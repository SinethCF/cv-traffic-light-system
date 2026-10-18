import time
import requests
from smbus2 import SMBus
import tm1637

# --- QUICK HARDWARE CONNECTION SETUP ---
# Connect the MCP23017 boards to the Raspberry Pi via I2C (SDA, SCL)
# MCP1 to control North and South lanes, and MCP2 to control East and West lanes.
# MCP1 (0x20) -> North_1 (A0 = Red, A1 = Yellow, A2 = Green), North_2 (A3 = Red, A4 = Yellow, A5 = Green)
# MCP1 (0x20) -> South_1 (B0 = Red, B1 = Yellow, B2 = Green), South_2 (B3 = Red, B4 = Yellow, B5 = Green)
# MCP2 (0x21) -> East_1 (A0 = Red, A1 = Yellow, A2 = Green), East_2 (A3 = Red, A4 = Yellow, A5 = Green)
# MCP2 (0x21) -> West_1 (B0 = Red, B1 = Yellow, B2 = Green), West_2 (B3 = Red, B4 = Yellow, B5 = Green)

# The TM1637 7-segment displays are connected to GPIO pins (CLK, DIO) on the Raspberry Pi to display countdown timers for each lane.

# --- CONFIGURATION ---
API_URL = "http://127.0.0.1:8080/api/counts"
SAFE_TIMEOUT = 10.0  # Seconds before hardware assumes the AI system is down

# I2C Addresses for the two modified MCP23017 boards
MCP_1 = 0x20  # Handles North and South
MCP_2 = 0x21  # Handles East and West

# MCP23017 Register Addresses
IODIRA = 0x00   # Direction register for Bank A (0 = Output, 1 = Input)
IODIRB = 0x01   # Direction register for Bank B (0 = Output, 1 = Input)
GPIOA  = 0x12   # Register for Bank A (Write)
GPIOB  = 0x13   # Register for Bank B (Write)

# LED Hex Values (Wired to Pins 0,1,2 for Lane 1 & Pins 3,4,5 for Lane 2)
L1_RED = 0x01
L1_YEL = 0x02
L1_GRN = 0x04

L2_RED = 0x08
L2_YEL = 0x10
L2_GRN = 0x20

# TM1637 7-Segment Hex Map (Used to build custom 4-digit arrays safely)
SEGMENTS = {
    '0': 0x3f, '1': 0x06, '2': 0x5b, '3': 0x4f, '4': 0x66,
    '5': 0x6d, '6': 0x7d, '7': 0x07, '8': 0x7f, '9': 0x6f,
    ' ': 0x00, '-': 0x40
}

# The 6 Collision-Free Configurations (Mirrored from the Brain)
CONFIGS = {
    "C1": ["North_2", "South_2"], "C2": ["East_2", "West_2"],
    "C3": ["North_1", "North_2"], "C4": ["South_1", "South_2"],
    "C5": ["West_1", "West_2"],   "C6": ["East_1", "East_2"]
}

# --- INITIALIZE I2C HARDWARE ---
bus = SMBus(1)
for mcp in [MCP_1, MCP_2]:
    try:
        # Set all Bank A and Bank B pins to OUTPUT
        bus.write_byte_data(mcp, IODIRA, 0x00)
        bus.write_byte_data(mcp, IODIRB, 0x00)
        # Turn all LEDs OFF initially
        bus.write_byte_data(mcp, GPIOA, 0x00)
        bus.write_byte_data(mcp, GPIOB, 0x00)
    except OSError:
        print(f"CRITICAL: Failed to reach MCP23017 at {hex(mcp)}!")

# --- INITIALIZE DISPLAYS ---
# Update these GPIO pins to match wherever you wired the 4 modules!
displays = {
    "North": tm1637.TM1637(clk=5, dio=6),
    "East":  tm1637.TM1637(clk=17, dio=27),
    "South": tm1637.TM1637(clk=22, dio=23),
    "West":  tm1637.TM1637(clk=24, dio=25)
}
for d in displays.values():
    d.brightness = 7
    # Write blank characters, but turn ON the colon (0x80) on the second digit
    d.write([0x00, 0x80, 0x00, 0x00])

# --- HELPER FUNCTIONS ---
def get_lane_hex(lane, position, active_config, phase, green_holds):
    """Determines the color for a lane and returns its hex pin value."""
    # Determine the required color based on the current state
    if lane in green_holds:     # First priority: Override to solid green if in the green_holds list
        color = "GREEN"
    elif lane in CONFIGS[active_config]:
        if phase == "GREEN": color = "GREEN"
        elif phase == "STOPPING": color = "YELLOW"
        elif phase == "PREPARING": color = "RED_YELLOW"
        else: color = "RED"
    else:
        color = "RED"

    # Map the color to the correct pins based on if it's Lane 1 or Lane 2
    if position == 1:
        if color == "GREEN": return L1_GRN
        if color == "YELLOW": return L1_YEL
        if color == "RED_YELLOW": return L1_RED | L1_YEL
        return L1_RED
    else:
        if color == "GREEN": return L2_GRN
        if color == "YELLOW": return L2_YEL
        if color == "RED_YELLOW": return L2_RED | L2_YEL
        return L2_RED

def get_display_segments(lane, active_config, locked_next, display_active, display_next, blank_lanes):
    """Converts the JSON text into a 2-byte array for half of a TM1637 screen."""
    if lane in blank_lanes:
        text = "  "  # Force blank for lanes in the blank_lanes override
    elif lane in CONFIGS[active_config]:
        text = str(display_active)
    elif lane in CONFIGS[locked_next]:
        text = str(display_next)
    else:
        text = "  " # Blank for resting lanes
        
    # Pad single digits with a space so "5" becomes " 5"
    text = text.rjust(2, ' ')
    
    # Return the raw hex segments for the two characters
    return [SEGMENTS.get(text[0], 0x00), SEGMENTS.get(text[1], 0x00)]

# --- MAIN CONTROL LOOP ---
print("Starting Hardware Integration Service...")

# The trackers
last_successful_ping = time.time()
last_known_heartbeat = 0.0
fallback_active = False

# --- SAFE DEFAULT STATE ---
state = {
    "active_config": "C1", "locked_next": "C2", 
    "phase": "RED", "display_active": "  ", "display_next": "  "
}

try:
    while True:
        # Attempt to fetch the latest state from the AI Brain
        try:
            # Fetch Latest State from the AI Brain
            response = requests.get(API_URL, timeout=1.0)
            data = response.json()
            state = data['state']

            # Extract the new heartbeat stamp
            current_heartbeat = data.get('heartbeat', 0.0)

            # If the heartbeat has changed, the YOLO brain is alive!
            if current_heartbeat != last_known_heartbeat:
                # If successful, reset the timer!
                last_successful_ping = time.time()
                last_known_heartbeat = current_heartbeat

                if fallback_active:
                    print("AI Connection Restored & YOLO Active! Returning to normal operation.")
                    fallback_active = False

        except Exception as e:
            # No longer 'pass' blindly. We just let the loop evaluate the timeout below.
            pass

        # TIMER EVALUATION FOR FALLBACK MODE
        time_since_last = time.time() - last_successful_ping

        if time_since_last > SAFE_TIMEOUT:
            # --- CRITICAL HARDWARE FALLBACK MODE ---
            if not fallback_active:
                print(f"CRITICAL: AI lost for {SAFE_TIMEOUT}s. Entering Auto-Flash Mode.")
                fallback_active = True

            # Create a 1-second toggling blinker using system time
            # int() grabs the current whole second, % 2 toggles it every second.
            is_blink_on = int(time.time()) % 2 == 0
            
            # Combine Lane 1 Yellow and Lane 2 Yellow if blinking ON, else send 0x00 (OFF)
            if is_blink_on:
                yellow_all_hex = (L1_YEL | L2_YEL)
            else:
                yellow_all_hex = 0x00
            
            # Blast the identical blink command to all 4 banks instantly
            try:    # TRY EXCEPT for testing only! (Test 1)
                bus.write_byte_data(MCP_1, GPIOA, yellow_all_hex)
                bus.write_byte_data(MCP_1, GPIOB, yellow_all_hex)
                bus.write_byte_data(MCP_2, GPIOA, yellow_all_hex)
                bus.write_byte_data(MCP_2, GPIOB, yellow_all_hex)
            except OSError:
                pass  # If the MCP23017 is unreachable, we just skip this cycle

            # Turn off all 7-Segment display numbers, but keep the colon ON
            blank_screen = [0x00, 0x80, 0x00, 0x00]
            for d in displays.values():
                d.write(blank_screen)
        
        else:
            # --- NORMAL OPERATION MODE ---
            active = state['active_config']
            nxt = state['locked_next']
            phase = state['phase']
            d_act = state['display_active']
            d_nxt = state['display_next']

            # Extract the override commands (Defaults to empty list if missing)
            blank_lanes = state.get('blank_lanes', [])
            green_holds = state.get('green_holds', [])

            # First, update the MCP23017 boards with the correct LED states for each lane
            # Update MCP_1 (North and South Lanes)
            n_bank = get_lane_hex("North_1", 1, active, phase, green_holds) | get_lane_hex("North_2", 2, active, phase, green_holds)
            s_bank = get_lane_hex("South_1", 1, active, phase, green_holds) | get_lane_hex("South_2", 2, active, phase, green_holds)

            # Update MCP_2 (East and West Lanes)
            e_bank = get_lane_hex("East_1", 1, active, phase, green_holds) | get_lane_hex("East_2", 2, active, phase, green_holds)
            w_bank = get_lane_hex("West_1", 1, active, phase, green_holds) | get_lane_hex("West_2", 2, active, phase, green_holds)
            try:    # TRY EXCEPT for testing only! (Test 2)
                bus.write_byte_data(MCP_1, GPIOA, n_bank)
                bus.write_byte_data(MCP_1, GPIOB, s_bank)
                bus.write_byte_data(MCP_2, GPIOA, e_bank)
                bus.write_byte_data(MCP_2, GPIOB, w_bank)
            except OSError:
                pass  # If the MCP23017 is unreachable, we just skip this cycle

            # Next, update TM1637 Displays (4 Modules total)
            # North Display (Digits 1,2 = North_1 | Digits 3,4 = North_2)
            n_segs = get_display_segments("North_1", active, nxt, d_act, d_nxt, blank_lanes) + get_display_segments("North_2", active, nxt, d_act, d_nxt, blank_lanes)
            n_segs[1] |= 0x80  # Force the colon ON
            displays["North"].write(n_segs)

            # South Display (Digits 1,2 = South_1 | Digits 3,4 = South_2)
            s_segs = get_display_segments("South_1", active, nxt, d_act, d_nxt, blank_lanes) + get_display_segments("South_2", active, nxt, d_act, d_nxt, blank_lanes)
            s_segs[1] |= 0x80  # Force the colon ON
            displays["South"].write(s_segs)

            # East Display (Digits 1,2 = East_1 | Digits 3,4 = East_2)
            e_segs = get_display_segments("East_1", active, nxt, d_act, d_nxt, blank_lanes) + get_display_segments("East_2", active, nxt, d_act, d_nxt, blank_lanes)
            e_segs[1] |= 0x80  # Force the colon ON
            displays["East"].write(e_segs)

            # West Display (Digits 1,2 = West_1 | Digits 3,4 = West_2)
            w_segs = get_display_segments("West_1", active, nxt, d_act, d_nxt, blank_lanes) + get_display_segments("West_2", active, nxt, d_act, d_nxt, blank_lanes)
            w_segs[1] |= 0x80  # Force the colon ON
            displays["West"].write(w_segs)

        # Polling rate: 10 times per second
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\nShutting down hardware... clearing all pins.")

finally:
    try:
        bus.write_byte_data(MCP_1, GPIOA, 0x00)
        bus.write_byte_data(MCP_1, GPIOB, 0x00)
        bus.write_byte_data(MCP_2, GPIOA, 0x00)
        bus.write_byte_data(MCP_2, GPIOB, 0x00)
    except Exception as e:
        print(f"Error while clearing MCP23017: {e}")
    for d in displays.values():
        d.write([0, 0, 0, 0])