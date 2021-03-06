import time

from kafka.helper.Logger import Logger
from kafka.helper.date_helper import KerbalDate

class LaunchControl:

    @staticmethod
    def abort():
       Logger.log("Launch Aborted!!!!")
       exit()


    def __init__(self, vessel):
        self.vessel = vessel.vessel
        self.decorated = vessel

    def preflight_setup(self):

        self.engage_autopilot()
        self.vessel.control.sas = True
        self.vessel.control.rcs = True
        Logger.log("Control Go!")

    def countdown(self,count):

        Logger.log("Countdown sequence initiated")

        for i in range(1,count+1).__reversed__():
            Logger.log('{}...'.format(i))
            time.sleep(1)

        Logger.log('Launch!')

    def engage_autopilot(self):

        self.vessel.auto_pilot.target_pitch_and_heading(90, 90)
        self.vessel.auto_pilot.engage()

        Logger.log("Guidance Go!")


    def activate(self, count):

        self.preflight_setup()

        self.countdown(count)

        self.decorated.set_throttle(1.0)

        self.decorated.info.describe_current_stage_engines()

        #LaunchControl.abort()
        if self.vessel.thrust == 0.0:
            self.decorated.stage()
            self.decorated.info.describe_current_stage_engines()

        Logger.log(KerbalDate.get_instance_from_ut().to_string())

        while self.decorated.twr() < 1.2:
            Logger.log("TWR: {:.2f}".format(self.decorated.twr()))
            time.sleep(1.5)
            if self.decorated.has_no_thrust():
                self.decorated.set_throttle(1.0)
                time.sleep(2)

            if self.decorated.twr() == 0.0:
                Logger.log("No thrust attempt stage - probably needs to check for engine presence on current stage.")
              #  self.decorated.stage()
            elif self.decorated.max_stage_twr() < 1.2:
                Logger.log("Max available thrust is < 1.2 activating next stage.")
            #    self.decorated.stage()

        self.decorated.disengage_launch_clamps()
        self.launch_twr = self.decorated.max_stage_twr()



    def coast_to_altitude(self, target_altitude):
        #power down when approaching target altitude
        self.vessel.control.throttle = 0.25
        while self.decorated.apoapsis() < target_altitude:
            pass

        #throttle off
        Logger.log("Target altitude reached")
        self.vessel.control.throttle = 0

        # Wait until out of atmosphere
        Logger.log('Coasting out of atmosphere')
        while self.decorated.altitude() < 70500:
            pass

    def control_low_orbit_thrust(self):
        speed = self.vessel.flight(self.vessel.orbit.body.reference_frame).speed
        if self.decorated.altitude() < 10000 and speed > 200.:
            self.decorated.set_throttle(float(0.5))
        elif speed < 200:
            self.decorated.set_throttle(1)

    def gravity_turn(self, turn_start_altitude, turn_end_altitude, target_altitude):
        Logger.log("Beginning Gravity turn")

        turn_angle=0

        while True:

            self.decorated.log_flight_data()

            #Gravity Turn
            self.control_pitch_and_heading_mk2(turn_angle, turn_end_altitude, turn_start_altitude)

            # Separate SRBs when finished
            self.check_and_perform_staging()

            if self.is_target_altitude_approaching(target_altitude):
                Logger.log('Approaching target apoapsis')
                break

        self.coast_to_altitude(target_altitude)

    def is_target_altitude_approaching(self, target_altitude):
        return self.decorated.apoapsis() > target_altitude * 0.9

    def check_and_perform_staging(self):

        if self.decorated.is_decouple_stage_resources_exhausted() or self.decorated.has_no_thrust():
            Logger.log("stage exhausted: {}, stage thrust {}".format(self.decorated.is_decouple_stage_resources_exhausted(),not self.decorated.has_no_thrust()))
            self.decorated.stage()

            while self.decorated.has_no_thrust() and not self.decorated.is_decouple_stage_resources_exhausted():
                Logger.log("No thrust! Probably separate stage and engine lets try again.")
                time.sleep(1)
                self.decorated.stage()



    #This uses the function from the krpc tutorial
    def control_pitch_and_heading(self, turn_angle, turn_end_altitude, turn_start_altitude):

        altitude = self.decorated.altitude()
        if turn_start_altitude < altitude < turn_end_altitude:
            frac = (altitude - turn_start_altitude) / (turn_end_altitude - turn_start_altitude)
            new_turn_angle = frac * 90

            if abs(new_turn_angle - turn_angle) > 0.5:
                turn_angle = new_turn_angle
                self.vessel.auto_pilot.target_pitch_and_heading(90 - turn_angle, 90)

    # Alternative based on https://imgur.com/a/SXttd
    # https://www.reddit.com/r/KerbalSpaceProgram/comments/4b87lx/how_to_launch_rockets_efficiently_in_ksp_105_and/
    # https://www.reddit.com/r/KerbalSpaceProgram/comments/4b87lx/how_to_launch_rockets_efficiently_in_ksp_105_and/d17q1yr
    #
    #
    # turnEnd = 9000*launchTWR + 35000
    # turnExponent = MAX(1 / (2.25*launchTWR - 1.35), 0.25)
    # PitchAngle = 90 * (1 - (CurrentAlt / TurnEnd) ^ TurnExponent)
    def control_pitch_and_heading_mk2(self, turn_angle, turn_end_altitude, turn_start_altitude):
        altitude = self.decorated.altitude()
        turn_end = 9000 * self.launch_twr + 35000
        turn_exponent = max(1 / (2.25 * self.launch_twr - 1.35), 0.25)

        if turn_start_altitude < altitude < turn_end:
            frac = (1 - (altitude / turn_end) ** turn_exponent)
            new_turn_angle = frac * 90

            if abs(new_turn_angle - turn_angle) > 0.5:
                turn_angle = new_turn_angle
                self.vessel.auto_pilot.target_pitch_and_heading(90 - turn_angle, 90)