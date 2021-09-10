from .register import *
from .definitions import *


def not_supported(value):
	'''
	Shortcut to inform that the selected READ or WRITE operation is not supported on the register.
	'''
	raise ValueError('Operation not supported from register')


class Converters:
	'''
	Standard data converters to be reused in register definitions
	'''
	ENCODING = 'UTF-8'

	BOOLEAN_CONVERTER_FROM = lambda device_value : True if (device_value[0] & 0x01) else False
	BOOLEAN_CONVERTER_TO = lambda local_value : [0x01 if local_value else 0x00]
	NOT_SUPPORTED = lambda value: not_supported(value)
	ASCII = lambda value: value.decode(Converters.ENCODING)
	HEX_STRING = lambda bs: ':'.join(['%02x'%b for b in bs]).upper()
	SINGLE_INTEGER = lambda value: value[0]
	SINGLE_16B_INTEGER = lambda value: value[0]*256+value[1]
	INTEGER_ARRAY = lambda value: [int(v) for v in value]
	INTEGER_TUPLE = lambda value: tuple([int(v) for v in value]) 


class Registers:
	'''
	Contains all registers definitions.

	A register is a combination of:
	- characteristic
	- data converter for READ
	- data converter for WRITE
	
	This layer prevents the main client from having to deal with low-level data conversion.
	'''
	
	KEY_STATE = Register(
		'KEY STATE', Characteristics.KEY_STATE,
		Converters.BOOLEAN_CONVERTER_FROM, Converters.NOT_SUPPORTED )

	MOTOR_SPEED = Register(
		'MOTOR SPEED', Characteristics.MOTOR_CONTROL, 
		lambda device_value : tuple([device_value[1], device_value[2]]),
		lambda local_value : [0x01, local_value[0], local_value[1]] )

	MOTOR_STOP = Register(
		'MOTOR STOP', Characteristics.MOTOR_CONTROL, 
		Converters.NOT_SUPPORTED, lambda local_value : [0x01, 0x00, 0x00] )

	SHUTDOWN = Register(
		'SHUTDOWN', Characteristics.MOTOR_CONTROL, 
		Converters.NOT_SUPPORTED, lambda local_value : [0x01, 0xFA] )

	VERIFY_ACCELEROMETER = Register(
		'VERIFY ACCELEROMETER', Characteristics.MOTOR_CONTROL, 
		Converters.NOT_SUPPORTED, lambda local_value : [0xFF, 0xFF, 0xFF] )

	MOTOR_WORK_ON_TOUCH = Register(
		'MOTOR WORK ON TOUCH', Characteristics.MOTOR_WORK_ON_TOUCH, 
		lambda device_value : True if device_value[0] == CruiseControlStatus.ENABLED else False, 
		lambda local_value : [local_value] )

	VIBRATOR_SETTING = Register(
		'VIBRATOR SETTING', Characteristics.VIBRATOR_SETTING, 
		Converters.INTEGER_TUPLE, Converters.INTEGER_ARRAY )

	WAKE_UP = Register(
		'WAKE UP', Characteristics.WAKE_UP, 
		lambda device_value : True if device_value[0] == WakeUp.ENABLED else False, 
		lambda local_value : [WakeUp.ENABLED if local_value else WakeUp.DISABLED] )

	HALL = Register(
		'HALL', Characteristics.HALL, 
		Converters.SINGLE_16B_INTEGER, Converters.NOT_SUPPORTED )

	LENGTH = Register(
		'LENGTH', Characteristics.LENGTH, 
		Converters.SINGLE_16B_INTEGER, Converters.NOT_SUPPORTED )

	ACCELEROMETER = Register(
		'ACCELEROMETER', Characteristics.ACCELEROMETER, 
		lambda device_value : tuple([
			device_value[0]*256+device_value[1],
			device_value[2]*256+device_value[3],
			device_value[4]*256+device_value[5] ]), 
		Converters.NOT_SUPPORTED )

	PRESSURE_TEMPERATURE = Register(
		'PRESSURE_TEMPERATURE', Characteristics.PRESSURE, 
		lambda device_value : tuple([
			(device_value[0]*256*256+device_value[1]*256+device_value[2]) / 100.0,
			(device_value[4]*256*256*256+device_value[5]*256*256+device_value[6]*256+device_value[7]) / 100.0 ]), 
		Converters.NOT_SUPPORTED )

	BUTTON =  Register(
		'BUTTON', Characteristics.BUTTON, 
		Converters.SINGLE_INTEGER, Converters.NOT_SUPPORTED )

	USER_RECORD =  Register(
		'USER RECORD', Characteristics.USER_RECORD, 
		Converters.SINGLE_16B_INTEGER, Converters.NOT_SUPPORTED )

	USER_RECORD_RESET =  Register(
		'USER RECORD RESET', Characteristics.USER_RECORD,
		Converters.NOT_SUPPORTED, 
		lambda local_value : [0xEE] )

	MANUFACTURER_NAME = Register(
		'MANUFACTURER NAME', Characteristics.MANUFACTURER_NAME, 
		Converters.ASCII, Converters.NOT_SUPPORTED )

	MODEL_NUMBER = Register(
		'MODEL NUMBER', Characteristics.MODEL_NUMBER, 
		Converters.ASCII, Converters.NOT_SUPPORTED )
	
	HARDWARE_REVISION = Register( 
		'HARDWARE REVISION', Characteristics.HARDWARE_REVISION, 
		Converters.ASCII, Converters.NOT_SUPPORTED )

	FIRMWARE_REVISION = Register( 
		'FIRMWARE REVISION', Characteristics.FIRMWARE_REVISION, 
		Converters.ASCII, Converters.NOT_SUPPORTED )

	SOFTWARE_REVISION = Register( 
		'SOFTWARE REVISION', Characteristics.SOFTWARE_REVISION, 
		Converters.ASCII, Converters.NOT_SUPPORTED )

	MAC_ADDRESS = Register( 
		'MAC ADDRESS', Characteristics.MAC_ADDRESS, 
		Converters.HEX_STRING, Converters.NOT_SUPPORTED )
	
	SERIAL_NUMBER = Register( 
		'SERIAL NUMBER', Characteristics.SERIAL_NUMBER, 
		Converters.HEX_STRING, Converters.NOT_SUPPORTED )
	
	BATTERY_LEVEL = Register( 
		'BATTERY LEVEL', Characteristics.BATTERY_LEVEL, 
		Converters.SINGLE_INTEGER, Converters.NOT_SUPPORTED )
		
	CHIP_ID = Register( 
		'CHIP ID', Characteristics.CHIP_ID, 
		Converters.HEX_STRING, Converters.NOT_SUPPORTED )
	
	GENERIC_ACCESS_DEVICE_NAME = Register( 
		'DEVICE NAME', Characteristics.GENERIC_ACCESS_DEVICE_NAME, 
		Converters.ASCII, Converters.NOT_SUPPORTED )
	
	GENERIC_ACCESS_APPEARANCE = Register( 
		'APPEARANCE', Characteristics.GENERIC_ACCESS_APPEARANCE, 
		Converters.HEX_STRING, Converters.NOT_SUPPORTED )
	
	GENERIC_ACCESS_PERIPHERAL_PREFERRED_CONNECTION_PARAMETERS = Register( 
		'PPCP', Characteristics.GENERIC_ACCESS_PERIPHERAL_PREFERRED_CONNECTION_PARAMETERS, 
		Converters.HEX_STRING, Converters.NOT_SUPPORTED )
	 
	DEVICE_INFORMATION_SYSTEM_ID = Register( 
		'SYSTEM ID', Characteristics.DEVICE_INFORMATION_SYSTEM_ID, 
		Converters.HEX_STRING, Converters.NOT_SUPPORTED )
	
	DEVICE_INFORMATION_SERIAL_NUMBER_STRING = Register( 
		'SERIAL NUMBER STRING', Characteristics.DEVICE_INFORMATION_SERIAL_NUMBER_STRING, 
		Converters.ASCII, Converters.NOT_SUPPORTED )
	
	DEVICE_INFORMATION_IEEE11073 = Register( 
		'IEEE11073', Characteristics.DEVICE_INFORMATION_IEEE11073, 
		Converters.HEX_STRING, Converters.NOT_SUPPORTED )
	
	DEVICE_INFORMATION_PNP_ID = Register( 
		'PNP ID', Characteristics.DEVICE_INFORMATION_PNP_ID, 
		Converters.HEX_STRING, Converters.NOT_SUPPORTED )
	
	SECURITY_ACCESS = Register(
		'SECURITY_ACCESS', Characteristics.SECURITY_ACCESS,
		Converters.INTEGER_TUPLE, Converters.INTEGER_TUPLE )
