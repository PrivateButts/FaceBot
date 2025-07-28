"""
Python implementation of PCA9685 servo controller for pan-tilt mount.
This module provides direct I2C communication with the PCA9685 chip
and can be extended for additional I2C devices.
"""

import time
import logging
from typing import Optional
from dataclasses import dataclass

try:
    import smbus2
except ImportError:
    smbus2 = None
    # logging.warning("smbus2 not available. Servo control will be simulated.")


# PCA9685 Register Addresses
class PCA9685Registers:
    MODE1 = 0x00
    MODE2 = 0x01
    PRESCALE = 0xFE
    LED0_ON_L = 0x06
    LED0_ON_H = 0x07
    LED0_OFF_L = 0x08
    LED0_OFF_H = 0x09


# Servo Configuration Constants
@dataclass
class ServoConfig:
    """Configuration for servo channels"""

    SERVO_UP_CH = 0  # Up/Down movement channel
    SERVO_DOWN_CH = 1  # Left/Right movement channel

    # Servo angle limits
    SERVO_UP_MAX = 145
    SERVO_UP_MIN = 15
    SERVO_DOWN_MAX = 180
    SERVO_DOWN_MIN = 0

    # Movement settings
    STEP = 1
    STEP_DELAY = 0.002  # 2ms delay between steps

    # I2C settings
    I2C_BUS = 1  # Default I2C bus on Raspberry Pi
    I2C_ADDR = 0x40  # Default PCA9685 address


class PCA9685Controller:
    """
    Python implementation of PCA9685 PWM controller for servo control.
    Based on the original C implementation but with Python I2C libraries.
    """

    def __init__(
        self,
        bus_number: int = ServoConfig.I2C_BUS,
        address: int = ServoConfig.I2C_ADDR,
        simulate: bool = False,
    ):
        """
        Initialize the PCA9685 controller.

        Args:
            bus_number: I2C bus number (usually 1 on Raspberry Pi)
            address: I2C address of PCA9685 (default 0x40)
            simulate: If True, simulate operations without real hardware
        """
        self.bus_number = bus_number
        self.address = address
        self.simulate = simulate or smbus2 is None
        self.bus = None

        # Current servo positions
        self.servo_up_degree = 90
        self.servo_down_degree = 90

        if not self.simulate:
            try:
                self.bus = smbus2.SMBus(bus_number)
                self._initialize_pca9685()
                logging.info(
                    f"PCA9685 initialized on bus {bus_number}, address 0x{address:02x}"
                )
            except Exception as e:
                logging.error(f"Failed to initialize I2C: {e}")
                self.simulate = True
                logging.warning("Falling back to simulation mode")
        else:
            logging.info("PCA9685 running in simulation mode")

    def _write_register(self, register: int, value: int) -> bool:
        """Write a value to a PCA9685 register"""
        if self.simulate:
            logging.debug(f"SIMULATE: Write 0x{value:02x} to register 0x{register:02x}")
            return True

        try:
            self.bus.write_byte_data(self.address, register, value)
            return True
        except Exception as e:
            logging.error(f"Failed to write register 0x{register:02x}: {e}")
            return False

    def _read_register(self, register: int) -> Optional[int]:
        """Read a value from a PCA9685 register"""
        if self.simulate:
            logging.debug(f"SIMULATE: Read from register 0x{register:02x}")
            return 0x00  # Return dummy value

        try:
            return self.bus.read_byte_data(self.address, register)
        except Exception as e:
            logging.error(f"Failed to read register 0x{register:02x}: {e}")
            return None

    def _initialize_pca9685(self):
        """Initialize PCA9685 with default settings"""
        # Reset and configure MODE1 register
        self._write_register(PCA9685Registers.MODE1, 0x00)
        time.sleep(0.005)  # 5ms delay

        # Set PWM frequency to 60Hz (suitable for servos)
        self.set_pwm_frequency(60.0)

    def set_pwm_frequency(self, frequency: float):
        """
        Set the PWM frequency for all channels.

        Args:
            frequency: Desired frequency in Hz (typically 50-60Hz for servos)
        """
        frequency *= 0.8449  # Correct for frequency overshoot

        # Calculate prescaler value
        prescale_val = 25000000.0  # 25MHz oscillator
        prescale_val /= 4096.0  # 4096 PWM cycles
        prescale_val /= frequency
        prescale_val -= 1.0
        prescale = int(prescale_val + 0.5)

        # Read current MODE1 register
        old_mode = self._read_register(PCA9685Registers.MODE1)
        if old_mode is None:
            old_mode = 0x00

        # Put PCA9685 to sleep and set prescaler
        new_mode = (old_mode & 0x7F) | 0x10  # Sleep mode
        self._write_register(PCA9685Registers.MODE1, new_mode)
        self._write_register(PCA9685Registers.PRESCALE, prescale)
        self._write_register(PCA9685Registers.MODE1, old_mode)
        time.sleep(0.005)

        # Turn on auto-increment
        self._write_register(PCA9685Registers.MODE1, old_mode | 0xA0)

    def set_pwm(self, channel: int, on: int, off: int):
        """
        Set PWM values for a specific channel.

        Args:
            channel: PWM channel (0-15)
            on: Turn-on time (0-4095)
            off: Turn-off time (0-4095)
        """
        if channel < 0 or channel > 15:
            logging.error(f"Invalid channel: {channel}")
            return False

        base_reg = PCA9685Registers.LED0_ON_L + 4 * channel

        self._write_register(base_reg, on & 0xFF)
        self._write_register(base_reg + 1, on >> 8)
        self._write_register(base_reg + 2, off & 0xFF)
        self._write_register(base_reg + 3, off >> 8)

        return True

    def set_servo_pulse(self, channel: int, pulse_ms: float):
        """
        Set servo pulse width in milliseconds.

        Args:
            channel: Servo channel (0-15)
            pulse_ms: Pulse width in milliseconds (typically 1.0-2.0ms)
        """
        # Convert pulse width to PWM value
        period_ms = 1000.0 / 60.0  # Period length at 60Hz
        pulse_value = int((pulse_ms / period_ms) * 4096)
        self.set_pwm(channel, 0, pulse_value)

    def set_servo_degree(self, channel: int, degree: int):
        """
        Set servo position in degrees.

        Args:
            channel: Servo channel (0-15)
            degree: Angle in degrees (0-180)
        """
        # Constrain degree value
        degree = max(0, min(180, degree))

        # Convert degree to pulse width (1.0ms to 2.0ms range)
        # Standard servo: 0° = 1ms, 90° = 1.5ms, 180° = 2ms
        pulse_ms = 1.0 + (degree / 180.0)
        self.set_servo_pulse(channel, pulse_ms)

        # Update internal position tracking
        if channel == ServoConfig.SERVO_UP_CH:
            self.servo_up_degree = degree
        elif channel == ServoConfig.SERVO_DOWN_CH:
            self.servo_down_degree = degree

        logging.debug(f"Set servo {channel} to {degree}°")


class ServoController:
    """
    High-level servo controller for pan-tilt operations.
    Provides easy-to-use methods for controlling the pan-tilt mount.
    """

    def __init__(self, simulate: bool = False):
        """
        Initialize the servo controller.

        Args:
            simulate: If True, run in simulation mode without hardware
        """
        self.pca9685 = PCA9685Controller(simulate=simulate)
        self.config = ServoConfig()

        # Initialize servos to center position
        self.reset_position()

    def reset_position(self):
        """Reset both servos to center position (90 degrees)"""
        self.set_pan(90)
        self.set_tilt(90)
        logging.info("Servos reset to center position")

    def set_pan(self, degree: int) -> bool:
        """
        Set pan (left-right) position.

        Args:
            degree: Angle in degrees (0-180, where 90 is center)

        Returns:
            True if successful, False otherwise
        """
        degree = max(
            self.config.SERVO_DOWN_MIN, min(self.config.SERVO_DOWN_MAX, degree)
        )

        self.pca9685.set_servo_degree(self.config.SERVO_DOWN_CH, degree)
        return True

    def set_tilt(self, degree: int) -> bool:
        """
        Set tilt (up-down) position.

        Args:
            degree: Angle in degrees (15-145, where 90 is center)

        Returns:
            True if successful, False otherwise
        """
        degree = max(self.config.SERVO_UP_MIN, min(self.config.SERVO_UP_MAX, degree))

        self.pca9685.set_servo_degree(self.config.SERVO_UP_CH, degree)
        return True

    def pan_left(self, step: Optional[int] = None) -> bool:
        """Move pan servo left by specified step"""
        step = step or self.config.STEP
        new_degree = self.pca9685.servo_down_degree - step
        return self.set_pan(new_degree)

    def pan_right(self, step: Optional[int] = None) -> bool:
        """Move pan servo right by specified step"""
        step = step or self.config.STEP
        new_degree = self.pca9685.servo_down_degree + step
        return self.set_pan(new_degree)

    def tilt_up(self, step: Optional[int] = None) -> bool:
        """Move tilt servo up by specified step"""
        step = step or self.config.STEP
        new_degree = self.pca9685.servo_up_degree + step
        return self.set_tilt(new_degree)

    def tilt_down(self, step: Optional[int] = None) -> bool:
        """Move tilt servo down by specified step"""
        step = step or self.config.STEP
        new_degree = self.pca9685.servo_up_degree - step
        return self.set_tilt(new_degree)

    def get_position(self) -> dict:
        """
        Get current servo positions.

        Returns:
            Dictionary with 'pan' and 'tilt' keys containing current angles
        """
        return {
            "pan": self.pca9685.servo_down_degree,
            "tilt": self.pca9685.servo_up_degree,
        }

    def move_to_position(
        self,
        pan: Optional[int] = None,
        tilt: Optional[int] = None,
        smooth: bool = False,
    ) -> bool:
        """
        Move to absolute position with optional smooth movement.

        Args:
            pan: Target pan angle (None to keep current)
            tilt: Target tilt angle (None to keep current)
            smooth: If True, move gradually to target position

        Returns:
            True if successful, False otherwise
        """
        current = self.get_position()
        target_pan = pan if pan is not None else current["pan"]
        target_tilt = tilt if tilt is not None else current["tilt"]

        if not smooth:
            # Direct movement
            success = True
            if pan is not None:
                success &= self.set_pan(target_pan)
            if tilt is not None:
                success &= self.set_tilt(target_tilt)
            return success

        # Smooth movement
        max_steps = max(
            abs(target_pan - current["pan"]), abs(target_tilt - current["tilt"])
        )

        if max_steps == 0:
            return True

        for step in range(max_steps):
            progress = (step + 1) / max_steps

            if pan is not None:
                intermediate_pan = int(
                    current["pan"] + (target_pan - current["pan"]) * progress
                )
                self.set_pan(intermediate_pan)

            if tilt is not None:
                intermediate_tilt = int(
                    current["tilt"] + (target_tilt - current["tilt"]) * progress
                )
                self.set_tilt(intermediate_tilt)

            time.sleep(self.config.STEP_DELAY)

        return True

    def close(self):
        """Clean up resources"""
        if hasattr(self.pca9685, "bus") and self.pca9685.bus:
            self.pca9685.bus.close()
        logging.info("Servo controller closed")


# Global servo controller instance
_servo_controller: Optional[ServoController] = None


def get_servo_controller(simulate: bool = False) -> ServoController:
    """
    Get or create the global servo controller instance.

    Args:
        simulate: If True, run in simulation mode

    Returns:
        ServoController instance
    """
    global _servo_controller
    if _servo_controller is None:
        _servo_controller = ServoController(simulate=simulate)
    return _servo_controller


def cleanup_servo_controller():
    """Clean up the global servo controller instance"""
    global _servo_controller
    if _servo_controller is not None:
        _servo_controller.close()
        _servo_controller = None


# Example usage and testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # Test the servo controller
    controller = ServoController(simulate=True)

    print("Testing servo controller...")
    print(f"Initial position: {controller.get_position()}")

    # Test basic movements
    controller.pan_left(10)
    controller.tilt_up(15)
    print(f"After movement: {controller.get_position()}")

    # Test absolute positioning
    controller.move_to_position(pan=45, tilt=120)
    print(f"After absolute move: {controller.get_position()}")

    # Test smooth movement
    controller.move_to_position(pan=135, tilt=60, smooth=True)
    print(f"After smooth move: {controller.get_position()}")

    # Reset and cleanup
    controller.reset_position()
    print(f"After reset: {controller.get_position()}")

    controller.close()
    print("Test completed!")
