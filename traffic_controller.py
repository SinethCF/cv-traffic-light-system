import time

class TrafficController:
    def __init__(self):
        # --- 1. ENGINEERING CONSTANTS ---
        self.MIN_TIME = 15.0
        self.MAX_TIME = 90.0
        self.k = 2.0         # Seconds per vehicle baseline
        self.w_n = 1.0       # Linear weight for vehicle count
        self.w_t = 0.005     # Quadratic weight for wait time

        # --- NEW: LANE CAPACITY ---
        self.MAX_LANE_CAPACITY = 16.0   # The physical limit of your camera view (equivalent to 16 cars)

        # --- 2. LANE MEMORY & TIMERS ---
        self.lanes = ["North_1", "North_2", "East_1", "East_2", 
                      "South_1", "South_2", "West_1", "West_2"]
        # Tracks how long vehicles have been waiting (in seconds)
        self.wait_timers = {lane: 0.0 for lane in self.lanes}

        # --- NEW: SATURATION MEMORY ---
        self.is_saturated = {lane: False for lane in self.lanes}
        self.fill_rates = {lane: 0.0 for lane in self.lanes} # Locks in the n/t rate
        
        # --- 3. THE 6 COLLISION-FREE CONFIGURATIONS ---
        self.configs = {
            "C1": ["North_2", "South_2"],
            "C2": ["East_2", "West_2"],
            "C3": ["North_1", "North_2"],
            "C4": ["South_1", "South_2"],
            "C5": ["West_1", "West_2"],
            "C6": ["East_1", "East_2"]
        }

        # --- 4. STATE MACHINE INITIALIZATION ---
        self.active_config = "C1"      # Position 1 (Currently Green)
        self.locked_next = "C2"        # Position 2 (Locked in for next Green)
        self.time_remaining = self.MIN_TIME
        self.last_tick = time.time()

    def calculate_green_time(self, active_lanes, counts):
        """Calculates fractional T_green bounded by MIN and MAX"""

        # --- NEW: EXTRAPOLATION ENGINE ---
        effective_counts = {}
        for lane in self.lanes:
            if self.is_saturated[lane]:
                # Extrapolate n: locked rate * total wait time
                extrapolated_n = self.fill_rates[lane] * self.wait_timers[lane]
                # Ensure it never drops below the physical capacity limit
                effective_counts[lane] = max(self.MAX_LANE_CAPACITY, extrapolated_n)
            else:
                effective_counts[lane] = counts[lane]

        n_winning = sum(effective_counts[lane] for lane in active_lanes)
        n_total = sum(effective_counts.values())
        
        # Prevent division by zero if intersection is totally empty
        if n_total == 0:
            return self.MIN_TIME 
            
        fraction = n_winning / n_total
        t_calc = (n_winning * self.k) * (1 + fraction)
        
        return max(self.MIN_TIME, min(self.MAX_TIME, t_calc))

    def get_priorities(self, counts):
        """Calculates P = w_n*n + w_t*t^2 using raw visible counts (Not extrapolated)"""
        scores = {}
        for config_id, candidate_lanes in self.configs.items():
            
            # Skip the config that already has the green light
            if config_id == self.active_config:
                continue 
            
            score = 0
            for lane in candidate_lanes:
                n = counts[lane] # Priority strictly uses visible count
                t = self.wait_timers[lane]
                # Calculates the score for this lane and adds it to the total score for the config
                score += (self.w_n * n) + (self.w_t * (t ** 2))
            scores[config_id] = score
        return scores

    def update(self, counts):
        """The main loop triggered every frame to evaluate the state"""
        current_time = time.time()
        dt = current_time - self.last_tick
        self.last_tick = current_time

        # 1. UPDATE WAIT TIMERS
        active_lanes = self.configs[self.active_config]
        for lane in self.lanes:
            # Update the saturation status of each lane
            if lane not in active_lanes and counts[lane] > 0:

                # Accumulate wait time only if there is at least 1 car waiting
                self.wait_timers[lane] += dt

                # --- NEW: SATURATION TRIGGER & RATE LOCK-IN ---
                if counts[lane] >= self.MAX_LANE_CAPACITY and not self.is_saturated[lane]:
                    self.is_saturated[lane] = True
                    # Lock in the rate = Max_Lane_Capacity / wait_time (safeguarding against div by zero)
                    safe_time = max(1.0, self.wait_timers[lane])
                    self.fill_rates[lane] = self.MAX_LANE_CAPACITY / safe_time

                # If YOLO corrects a glitch or cars leave on red, cancel the extrapolation!
                elif counts[lane] < self.MAX_LANE_CAPACITY and self.is_saturated[lane]:
                    self.is_saturated[lane] = False
                    self.fill_rates[lane] = 0.0

            elif lane not in active_lanes and counts[lane] == 0:
                # Reset wait timer if no cars are waiting
                self.wait_timers[lane] = 0.0
                self.is_saturated[lane] = False
                self.fill_rates[lane] = 0.0

            elif lane in active_lanes:
                # Instantly reset timers for lanes currently getting a green light
                self.wait_timers[lane] = 0.0 
                self.is_saturated[lane] = False
                self.fill_rates[lane] = 0.0

        # 2. TICK DOWN ACTIVE GREEN LIGHT
        self.time_remaining -= dt

        # 3. THE HANDOVER TRIGGER (When countdown hits 0)
        if self.time_remaining <= 0:
            # Shift Position 2 into Position 1
            self.active_config = self.locked_next
            
            # Calculate the new time allocation based on exact counts at this millisecond
            new_active_lanes = self.configs[self.active_config]
            self.time_remaining = self.calculate_green_time(new_active_lanes, counts)
            
            # Run the priority engine on the remaining 5 configs to lock in the new Position 2
            scores = self.get_priorities(counts)
            self.locked_next = max(scores, key=scores.get) 

        # Return the clean system state to app.py
        return {
            "active_config": self.active_config,
            "locked_next": self.locked_next,
            "countdown": max(0, int(self.time_remaining)),
            "saturation_status": self.is_saturated,
            "wait_timers": self.wait_timers
        }