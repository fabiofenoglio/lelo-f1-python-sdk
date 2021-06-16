
class Constants:
	'''
	Application constants and logger names.
	Exposition of logger names allow easy logging configuration
	'''

	LOGGER_NAME = 'lelo-f1-sdk-client'
	LOGGER_IO_NAME = LOGGER_NAME + '.io'
	LOGGER_CALLBACK_NAME = LOGGER_NAME + '.notification'
	LOGGER_SYNC_NAME = LOGGER_NAME + '.sync'
	LOGGER_SOCKET_SERVER_NAME = LOGGER_NAME + '.socket-server'
	LOGGER_FS_NAME = LOGGER_NAME + '.fs'
	ADVERTISING_DEVICE_NAMES = ['F1s', 'F1SV2A', 'F1SV2X']


class Characteristics:
	'''
	Contains characteristics identifiers (UUIDs) for the device.
	'''
	KEY_STATE = '00000a0f-'
	MOTOR_CONTROL = '0000fff1-'
	MANUFACTURER_NAME = '00002a29-'
	MODEL_NUMBER = '00002a24-'
	HARDWARE_REVISION = '00002a27-'
	FIRMWARE_REVISION = '00002a26-'
	SOFTWARE_REVISION = '00002a28-'
	MAC_ADDRESS = '00000a06-'
	SERIAL_NUMBER = '00000a05-'
	BATTERY_LEVEL = '00002a19-'
	MOTOR_WORK_ON_TOUCH = '00000aa5-'
	VIBRATOR_SETTING = '00000a0d-'
	WAKE_UP	= '00000aa1-'
	HALL = '00000aa3-'
	LENGTH = '00000a0b-'
	ACCELEROMETER = '00000a0c-'
	PRESSURE = '00000a0a-'
	BUTTON = '00000aa4-'
	USER_RECORD	= '00000a04-'
	CHIP_ID = '00000a07-'
	
	# unreadable (err. 2)
	BATTERY_VOLTAGE = '00000a00-'
	OTA	= '00000a08-'
	
	# reads [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
	ACTIVATE = '00000a0e-'

	# reads [0]
	ACCELEROMETER_CONTROL = '00000aa0-'

	# reads [0]
	HALL_CONTROL = '00000aa2-'

	# ServiceName: GenericAccess
	# CharacteristicName: DeviceName
	# reads [70, 49, 115] "F1s"
	GENERIC_ACCESS_DEVICE_NAME = '00002a00-'
	
	# ServiceName: GenericAccess
	# CharacteristicName: Appearance
	# reads [0, 0]
	GENERIC_ACCESS_APPEARANCE = '00002a01-'
	
	# ServiceName: GenericAccess
	# CharacteristicName: PeripheralPreferredConnectionParameters
	# reads [80, 0, 160, 0, 0, 0, 232, 3]
	GENERIC_ACCESS_PERIPHERAL_PREFERRED_CONNECTION_PARAMETERS = '00002a04-'
	
	# ServiceName: DeviceInformation
	# CharacteristicName: SystemId
	# reads [238, 91, 69, 0, 0, 227, 100, 196]
	DEVICE_INFORMATION_SYSTEM_ID = '00002a23-'
	
	# ServiceName: DeviceInformation
	# CharacteristicName: SerialNumberString
	# reads [83, 101, 114, 105, 97, 108, 32, 78, 117, 109, 98, 101, 114] "Serial Number"
	DEVICE_INFORMATION_SERIAL_NUMBER_STRING = '00002a25-'
	
	# ServiceName: DeviceInformation
	# CharacteristicName: Ieee11073_20601RegulatoryCertificationDataList
	# reads [254, 0, 101, 120, 112, 101, 114, 105, 109, 101, 110, 116, 97, 108]
	DEVICE_INFORMATION_IEEE11073 = '00002a2a-'
	
	# ServiceName: DeviceInformation
	# CharacteristicName: PnpId
	# reads [1, 13, 0, 0, 0, 16, 1]
	DEVICE_INFORMATION_PNP_ID = '00002a50-'


class Services:
	'''
	Contains services identifiers (UUIDs) for the device.
	Unused at the moment.
	'''
	GENERIC_ACCESS_PROFILE = '00001800-0000-1000-8000-00805f9b34fb' 
	GENERIC_ATTRIBUTE_PROFILE = '00001801-0000-1000-8000-00805f9b34fb' 
	DEVICE_INFORMATION = '0000180a-0000-1000-8000-00805f9b34fb'
	VENDOR_SPECIFIC = '0000fff0-0000-1000-8000-00805f9b34fb'
	BATTERY_SERVICE = '0000180f-0000-1000-8000-00805f9b34fb' 


class CruiseControlStatus:
	'''
	Alias for Cruise Control status.
	For internal use only: value is translated to boolean when accessed from client methods.
	Not that values ENABLE_AND_RESET supports write only
	'''
	DISABLED = 0x00
	ENABLED = 0x01
	ENABLE_AND_RESET = 0x02


class WakeUp:
	'''
	Alias for quick Wake-Up status.
	For internal use only: value is translated to boolean when accessed from client methods.
	'''
	DISABLED = 0x00
	ENABLED = 0x01


class Buttons:
	'''
	Alias for buttons status.
	'''
	NONE_PRESSED = 0x03
	CENTRAL = 0x00
	PLUS = 0x01
	MINUS = 0x02


class ConnectionProfile:
	'''
	Holds information on connected device
	'''
	address = None
	uuid = None
	name = None