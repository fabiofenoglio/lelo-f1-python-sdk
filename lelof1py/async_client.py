import asyncio
import bleak
import time
import logging
import threading

from .definitions import *
from .registers import *
from .callback_handler import *
from .helpers import *

# Synchronization handle for concurrent resource access
SYNC_LOCK = threading.Lock()
SECURITY_ACCESS_SYNC_LOCK = threading.Lock()


class AsyncClient(object):
	'''
	Asynchronous LELO F1 SDK client.
	Configurable with standard logging.
	BLE backend is based on Bleak module.
	'''
	
	logger = logging.getLogger(Constants.LOGGER_NAME)
	logger_io = logging.getLogger(Constants.LOGGER_IO_NAME)
	logger_callback = logging.getLogger(Constants.LOGGER_CALLBACK_NAME)

	adapter = None
	connected = False
	connected_address = None
	bleak_client = None
	user_handlers = dict()
	bleak_handlers = dict()
	callback_data_history = dict()
	
	key_state_check = True
	protocol = 1
	wrote_security_access = False

	def __init__(self):
		'''
		Instantiate the client. Takes no parameters.
		'''
		self.logger.debug('instantiating LELO F1 SDK client')
		self.adapter = bleak

	async def discover(self, timeout=1, address=None):
		'''
		Look for F1s devices. Filters by name == 'F1s'
		If an address is provided, it filters by address instead.
		The 'timeout' parameter specifices maximum time before giving up.
		'''
		found = []
		time_start = time.time()
		
		while not len(found) and time.time() - time_start < timeout:
			self.logger.debug('discovering nearby devices')
			all_devices = await self.adapter.discover()
			
			self.logger.debug('found %d nearby devices', len(all_devices))
			if address is not None:
				# filter by address
				for device in all_devices:
					if device.address == address:
						self.logger.info('discovery found device with correct address: %s', device.name)
						found.append(device)
				self.logger.debug('of which %i with correct address', len(found))

			else:
				# filter by name	
				for device in all_devices:
					if device.name in Constants.ADVERTISING_DEVICE_NAMES:
						self.logger.info('discovery found device with correct advertising name: %s, address=%s', device.name, device.address)
						found.append(device)
				self.logger.debug('of which %i with correct name', len(found))

		self.logger.debug('found a total of %i devices responding to criteria', len(found))
		self.logger.debug('discovery took %i seconds', int(time.time() - time_start))

		return found


	async def connect(self, address, timeout=1):
		'''
		Connects to device with given MAC address.
		The 'timeout' parameter specifices maximum time before giving up.
		'''
		if not address:
			raise ValueError('Address is required. Please provide MAC address of target device')
		time_start = time.time()
		
		# Using Bleak as backend
		client = bleak.BleakClient(address)
		connected = False
		err = None
		attempt_num = 0
		
		self.logger.info('connecting to device %s', address)

		while not connected and err is None:
			# Reattempts until timeout
			attempt_num = attempt_num + 1
			self.logger.debug('attempting connection to device with address %s', address)
			try:
				await client.connect()
				connected = True
			except Exception as e:
				self.logger.debug("connection attempt #%d failed: %s", attempt_num, e)
				if time.time() - time_start < timeout:
					# Sleep 250ms between attempts
					await asyncio.sleep(0.25)
				else:
					err = e
					self.logger.warning('connection attempt timed out')
		
		if not connected:
			# Raise last exception when giving up
			raise err if err is not None else ValueError('connection failed in an unexpected way')

		self.logger.info('succesfully connected to device %s', address)
		self.connected = True
		self.bleak_client = client
		self.connected_address = address
		self.wrote_security_access = False
		
		# Profiles
		self.logger.debug('profiling the device')
		try:
			await self._profile_device()
		except Exception as e:
			self.logger.exception('error profiling device: %s', e)
		
		# Pings (reading a DeviceInfo register) to verify communication
		self.logger.debug('verifying communication layer')
		await self.ping()

		return self.bleak_client
	
	
	async def _profile_device(self):
		'''
		Enumerates characteristics on the device
		'''
		self.logger.debug('profiling the device now')

		device_name = await self.get_model_number()
		self.protocol = 2 if 'V2' in device_name.upper() else 1
		self.logger.debug('discovering protocol from device name: %s => %s', device_name, str(self.protocol))

		profiling = await self.bleak_client.get_services()

		for k, v in profiling.characteristics.items():
			try:
				read_val = await self.bleak_client.read_gatt_char(k)
				read_val = ':'.join(['%02x'%b for b in read_val]).upper()
			except Exception as e:
				read_val = 'cannot read characteristic: ' + str(e)
			self.logger.debug('root characteristic %s -> %s = [%s]', k, v, read_val)

		for k, v in profiling.services.items():
			self.logger.debug('service %s -> %s', k, v.description)
			for v2 in v.characteristics:
				try:
					read_val = await self.bleak_client.read_gatt_char(v2.uuid)
					read_val = ':'.join(['%02x'%b for b in read_val]).upper()
				except Exception as e:
					read_val = 'cannot read service item: ' + str(e)
				self.logger.debug('\tcharacteristic %s = [%s]', v2, read_val)

				for v3 in v2.descriptors:
					self.logger.debug('\t\tdescriptor %s handle %d', v3, v3.handle)

		for k, v in vars(Registers).items():
			if not isinstance(v, Register):
				continue
			try:
				read_val = await self.bleak_client.read_gatt_char(v.address)
				read_val = ':'.join(['%02x'%b for b in read_val]).upper()
			except Exception as e:
				read_val = 'cannot read register: ' + str(e)
	
			self.logger.debug('REGISTER %s -> %s = [%s]', v.address, v.name, read_val)

	@synchronized(SYNC_LOCK)
	async def disconnect(self):
		'''
		Disconnects from device.
		Automatically cancels pending notifications.
		'''
		if not self.connected:
			self.logger.warning('client is not connected')
			return
		
		await self._shutdown_notifications()

		await self._disconnect()
	
	@synchronized(SYNC_LOCK)
	async def shutdown(self):
		'''
		Shutdown the device and disconnects.
		Automatically cancels pending notifications.
		'''
		await self.assert_authorized()

		await self._shutdown_notifications()

		self.logger.info('sending device shutdown signal')
		await self.write(Registers.SHUTDOWN, True)
		
		await self._disconnect()

	async def _disconnect(self):
		self.logger.info('disconnecting from device')

		if self.bleak_client:
			await self.bleak_client.disconnect()

		self.connected = False
		self.bleak_client = None
		self.connected_address = None

		self.logger.info('disconnected from device')

	async def _shutdown_notifications(self):
		'''
		Attempts cancellation of notification subscriptions.
		Fails silently in case of cancellation error.
		'''
		for register_key, callbacks in self.user_handlers.items():
			self.logger.debug('unregistering all callbacks for register %s', register_key)
			for callback_handler in callbacks:
				try:
					await self.unregister(callback_handler)
				except Exception as e2:
					self.logger.exception('error closing callback handler for register %s: %s', register_key, e2)

	def is_connected(self):
		'''
		Checks wether connection to the device is active
		'''
		return self.connected

	def assert_connected(self):
		'''
		Shortcut method to raise error if the device is not connected
		'''
		if not self.connected:
			raise ValueError('Client is not connected')
		
	async def is_authorized(self):
		'''
		Checks wether the user has authorized the connection by pressing the central button
		'''
		return self.is_connected() and await self.get_key_state(silent=True) 
	
	async def assert_authorized(self):
		'''
		Shortcut method to raise error if the connection has not been authorized by pressing the central button
		'''
		if self.key_state_check:
			if not await self.is_authorized():
				raise ValueError('Client is not authorized (KEY_STATE = 0). Press the central button to proceed')
		else:
			self.logger.debug('skipping key_state check because it is disabled')

	def enable_key_state_check(self):
		'''
		Enable check of KEY_STATE before attempting commands.
		'''
		self.key_state_check = True

	def disable_key_state_check(self):
		'''
		Disable check of KEY_STATE before attempting commands.
		'''
		self.key_state_check = False

	async def read(self, register, silent=False):
		'''
		Reads from the specified register.
		Automatically converts the data from device format to user format using the register configuration.
		The silent parameters allow to skip logging for recurrent background reads.
		'''
		self.assert_connected()
		
		if not register:
			raise ValueError('Register is required')

		self.logger_io.debug('READING %s %s', register.address, register.name)
		read_direct = await self.bleak_client.read_gatt_char(register.address)
		converted = register.from_device(read_direct, silent=silent)
		self.logger_io.info('READ %s %s >> %s', register.address, register.name, converted)
		return converted


	async def write(self, register, value=None):
		'''
		Writes to the specified register.
		Automatically converts the data from user format to device format using the register configuration.
		'''
		self.assert_connected()
		
		if not register:
			raise ValueError('Register is required')

		converted_value = register.to_device(value)

		self.logger_io.info('WRITE %s %s << %s', register.address, register.name, converted_value)
		
		try:
			await self.bleak_client.write_gatt_char(register.address, bytearray(converted_value))
		except Exception as e:
			self.logger_io.exception('error writing to %s: %s', register.address, e)
			raise e

		self.logger_io.info('WRITE %s %s DONE', register.address, register.name)


	async def get_manufacturer_name(self):
		'''
		Reads the manufacturer name.
		Returns an ASCII UTF-8 string
		'''
		self.assert_connected()
		
		return await self.read(Registers.MANUFACTURER_NAME)


	async def get_model_number(self):
		'''
		Reads the model number.
		Returns an ASCII UTF-8 string
		'''
		self.assert_connected()
		
		return await self.read(Registers.MODEL_NUMBER)


	async def get_hardware_revision(self):
		'''
		Reads the device hardware revision.
		Returns an ASCII UTF-8 string
		'''
		self.assert_connected()
		
		return await self.read(Registers.HARDWARE_REVISION)


	async def get_firmware_revision(self):
		'''
		Reads the device firmware revision.
		Returns an ASCII UTF-8 string
		'''
		self.assert_connected()
		
		return await self.read(Registers.FIRMWARE_REVISION)


	async def get_software_revision(self):
		'''
		Reads the device software revision.
		Returns an ASCII UTF-8 string
		'''
		self.assert_connected()
		
		return await self.read(Registers.SOFTWARE_REVISION)


	async def get_mac_address(self):
		'''
		Reads the device mac address.
		Returns an ASCII UTF-8 string in the format AA:BB:CC:DD:EE:FF
		'''
		self.assert_connected()
		
		return await self.read(Registers.MAC_ADDRESS)


	async def get_serial_number(self):
		'''
		Reads the device serial number.
		Returns an ASCII UTF-8 string in the format XX:......:YY
		'''
		self.assert_connected()
		
		return await self.read(Registers.SERIAL_NUMBER)


	async def get_chip_id(self):
		'''
		Reads the device CHIP ID.
		Returns an ASCII UTF-8 string in the format XX:......:YY
		'''
		self.assert_connected()
		
		return await self.read(Registers.CHIP_ID)


	async def get_device_name(self):
		'''
		Reads the device name.
		Returns an ASCII UTF-8 string
		'''
		self.assert_connected()
		
		# return await self.read(Registers.GENERIC_ACCESS_DEVICE_NAME)
		# macOS compatibility patch
		return await self.read(Registers.MODEL_NUMBER)


	async def get_system_id(self):
		'''
		Reads the system id.
		Returns an ASCII UTF-8 string in the format XX:......:YY
		'''
		self.assert_connected()
		
		return await self.read(Registers.DEVICE_INFORMATION_SYSTEM_ID)


	async def get_pnp_id(self):
		'''
		Reads the PNP id.
		Returns an ASCII UTF-8 string in the format XX:......:YY
		'''
		self.assert_connected()
		
		return await self.read(Registers.DEVICE_INFORMATION_PNP_ID)


	async def get_ieee_11073_20601(self):
		'''
		Reads the IEEE 11073 20601 regulation mandatory specification.
		Returns an ASCII UTF-8 string in the format XX:......:YY
		'''
		self.assert_connected()
		
		return await self.read(Registers.DEVICE_INFORMATION_IEEE11073)


	async def get_battery_level(self):
		'''
		Reads the battery level.
		Returns an integer from 0 to 100
		'''
		self.assert_connected()
		
		return await self.read(Registers.BATTERY_LEVEL)


	async def get_use_count(self):
		'''
		Reads the use count.
		Returns an integer.
		'''
		await self.assert_authorized()
		return await self.read(Registers.USER_RECORD)


	async def reset_use_count(self):
		'''
		Resets device use count to zero.
		'''
		await self.assert_authorized()
		self.logger.debug('resetting use count')
		return await self.write(Registers.USER_RECORD_RESET)


	async def get_buttons_status(self):
		'''
		Reads the button status. 
		Returns an int value from the enum Buttons:
			Buttons.NONE_PRESSED = 0x03
			Buttons.CENTRAL = 0x00
			Buttons.PLUS = 0x01
			Buttons.MINUS = 0x02
		'''
		await self.assert_authorized()
		return await self.read(Registers.BUTTON)


	async def get_temperature_and_pressure(self):
		'''
		Reads the device internal temperature and pressure.
		Returns a touple (temperature, pressure).
		Temperature is a floating point number with 2 decimals in Celsius degrees.
		Pressure is a floating point number with 2 decimals in mbar.
		Eg. (24.25, 987.23)
		'''
		await self.assert_authorized()
		return await self.read(Registers.PRESSURE_TEMPERATURE)


	async def get_temperature(self):
		'''
		Reads the device internal temperature.
		Returns a floating point number with 2 decimals in Celsius degrees.
		Eg. (24.25, 987.23)
		'''
		await self.assert_authorized()
		return (await self.read(Registers.PRESSURE_TEMPERATURE))[0]


	async def get_pressure(self):
		'''
		Reads the device internal pressure.
		Returns a floating point number with 2 decimals in mbar.
		Eg. 987.23
		'''
		await self.assert_authorized()
		return (await self.read(Registers.PRESSURE_TEMPERATURE))[1]


	async def get_accelerometer(self):
		'''
		Reads the device accelerometer data.
		Returns a touple (x, y, z) where x, y and z are integers.
		Eg. (10, 200, 1000)
		'''
		await self.assert_authorized()
		return await self.read(Registers.ACCELEROMETER)


	async def get_accelerometer_x(self):
		'''
		Reads the device accelerometer data for X axis.
		Returns an integer.
		'''
		await self.assert_authorized()
		return (await self.read(Registers.ACCELEROMETER))[0]


	async def get_accelerometer_y(self):
		'''
		Reads the device accelerometer data for Y axis.
		Returns an integer.
		'''
		await self.assert_authorized()
		return (await self.read(Registers.ACCELEROMETER))[1]


	async def get_accelerometer_z(self):
		'''
		Reads the device accelerometer data for Z axis.
		Returns an integer.
		'''
		await self.assert_authorized()
		return (await self.read(Registers.ACCELEROMETER))[2]


	async def get_depth(self):
		'''
		Reads the insertion depth level.
		Returns an integer from 0 to 8.
		'''
		await self.assert_authorized()
		return await self.read(Registers.LENGTH)


	async def get_rotation_speed(self):
		'''
		Reads the rotation speed from Hall sensors.
		Returns an integer representing the rotations per second.
		'''
		await self.assert_authorized()
		return await self.read(Registers.HALL)


	async def get_wake_up(self):
		'''
		Reads the quick wake-up status.
		Returns a boolean.
		'''
		await self.assert_authorized()
		return await self.read(Registers.WAKE_UP)


	async def enable_wake_up(self):
		'''
		Enables quick wake-up.
		'''
		await self.assert_authorized()
		value = True
		self.logger.info('setting wake-up to %s', value)
		return await self.write(Registers.WAKE_UP, value)


	async def disable_wake_up(self):
		'''
		Disables quick wake-up.
		'''
		await self.assert_authorized()
		value = False
		self.logger.info('setting wake-up to %s', value)
		return await self.write(Registers.WAKE_UP, value)


	async def get_vibration_setting(self):
		'''
		Reads the device auto vibration settings
		Returns a touple of 8 integers ranging from 0 to 100.
		'''
		await self.assert_authorized()
		return await self.read(Registers.VIBRATOR_SETTING)


	async def set_vibration_setting(self, value):
		'''
		Sets the auto vibration settings.
		Takes a collection of 8 integers ranging from 0 to 100.
		'''
		if not value:
			raise ValueError('Value is required')
		if len(value) != 8:
			raise ValueError('A collection of 8 elements is required')
		for v in value:
			if v < 0 or v > 100:
				raise ValueError('Value should be between 0 and 100')
		
		await self.assert_authorized()
		self.logger.info('setting vibration-setting to %s', value)
		return await self.write(Registers.VIBRATOR_SETTING, value)


	async def get_cruise_control(self):
		'''
		Reads the cruise control status.
		Returns a boolean.
		'''
		await self.assert_authorized()
		return await self.read(Registers.MOTOR_WORK_ON_TOUCH)


	async def disable_cruise_control(self):
		'''
		Disables cruise control.
		'''
		await self.assert_authorized()

		value = CruiseControlStatus.DISABLED
		self.logger.info('setting cruise-control to %s', value)
		return await self.write(Registers.MOTOR_WORK_ON_TOUCH, value)


	async def enable_cruise_control(self, reset=False):
		'''
		Enables cruise control.
		If reset=True is passed, resets motors speed to default value.
		'''
		await self.assert_authorized()

		value = CruiseControlStatus.ENABLE_AND_RESET if reset else CruiseControlStatus.ENABLE
		self.logger.info('setting cruise-control to %s', value)
		return await self.write(Registers.MOTOR_WORK_ON_TOUCH, value)

	async def get_key_state(self, silent=False):
		'''
		Reads the key state status.
		Returns a boolean.
		'''
		self.assert_connected()
		if not silent:
			self.logger.debug('checking key state')
		if self.protocol == 1:
			return await self.read(Registers.KEY_STATE, silent=silent)
		else:
			value = await self.read(Registers.SECURITY_ACCESS, silent=silent)
			
			if value == (1, 0, 0, 0, 0, 0, 0, 0):
				self.logger.debug('key state: 1, fully authorized')
				return True
			
			elif value == (0, 0, 0, 0, 0, 0, 0, 0):
				self.logger.debug('key state: 0, not authorized')
				self.logger.info('Not authorized. Please, PRESS THE CENTRAL BUTTON')
				return False
	
			else:
				self.logger.debug('key state: got password, checking for security access write')
				await self.write_security_access(value)
				return False

	@synchronized(SECURITY_ACCESS_SYNC_LOCK)
	async def write_security_access(self, value):
		if self.wrote_security_access:
			return False

		self.logger.debug('WRITING PASSWORD TO SECURITY ACCESS')
		await self.write(Registers.SECURITY_ACCESS, value)
		self.wrote_security_access = True
		self.logger.debug('WROTE PASSWORD TO SECURITY ACCESS')
		return True

	async def stop_motors(self):
		'''
		Stops both motors of the device.
		'''
		await self.assert_authorized()
		
		self.logger.info('sending motors stop signal')
		await self.write(Registers.MOTOR_STOP, True)


	async def verify_accelerometer(self):
		'''
		Puts the device into VERIFY ACCELEROMETER mode.
		'''
		await self.assert_authorized()
		self.logger.info('enterying accelerometer verification mode')
		return await self.write(Registers.VERIFY_ACCELEROMETER)
	
	
	async def get_motors_speed(self):
		'''
		Reads the two motors speed.
		Returns a touple (X, Y) with X being the main motor speed ranging from 0 to 100
		and Y being the vibrator motor speed ranging from 0 to 100
		'''
		await self.assert_authorized()
		return await self.read(Registers.MOTOR_SPEED)


	async def get_main_motor_speed(self):
		'''
		Reads the main motor speed.
		Returns an integer ranging from 0 to 100
		'''
		await self.assert_authorized()
		return (await self.read(Registers.MOTOR_SPEED))[0]


	async def get_vibration_speed(self):
		'''
		Reads the vibrator motor speed.
		Returns an integer ranging from 0 to 100
		'''
		await self.assert_authorized()
		return (await self.read(Registers.MOTOR_SPEED))[1]


	async def set_motors_speed(self, value):
		'''
		Set the two motors speed.
		Takes a collection of two elements (X, Y) 
		with X being the main motor speed ranging from 0 to 100
		and Y being the vibrator motor speed ranging from 0 to 100
		'''
		if not value:
			raise ValueError('Value is required')
		if len(value) != 2:
			raise ValueError('A collection of 2 elements is required')
		for v in value:
			if v < 0 or v > 100:
				raise ValueError('Value should be between 0 and 100')
		
		await self.assert_authorized()
		self.logger.info('setting motor speed to %d and vibration speed to %d', value[0], value[1])
		return await self.write(Registers.MOTOR_SPEED, value)


	async def set_main_motor_speed(self, value):
		'''
		Sets the main motor speed.
		Takes an integer ranging from 0 to 100
		'''
		if value is None:
			raise ValueError('Value is required')
		if value < 0 or value > 100:
			raise ValueError('Value should be between 0 and 100')
		
		await self.assert_authorized()
		self.logger.info('setting main motor speed to %d', value)
		current_value = await self.get_vibration_speed();
		self.logger.debug('will mantain current vibration speed of %d', current_value)
		return await self.write(Registers.MOTOR_SPEED, [value, current_value])


	async def set_vibration_speed(self, value):
		'''
		Sets the vibrator motor speed.
		Takes an integer ranging from 0 to 100
		'''
		if value is None:
			raise ValueError('Value is required')
		if value < 0 or value > 100:
			raise ValueError('Value should be between 0 and 100')
		
		await self.assert_authorized()
		self.logger.info('setting vibration speed to %d', value)
		current_value = await self.get_main_motor_speed();
		self.logger.debug('will mantain current motor speed of %d', current_value)
		return await self.write(Registers.MOTOR_SPEED, [current_value, value])


	async def ping(self):
		'''
		Reads from a register to test device communication
		'''
		self.assert_connected()

		self.logger.debug('sending ping to device')
		await self.read(Registers.MODEL_NUMBER, silent=True)
		self.logger.debug('device responded to ping')
	
	
	async def notify_key_state(self, user_callback, distinct_until_changed=True):
		'''
		Subscribes to key state change notification.
		Requires a callback that accepts a boolean representing the key state value.
		Returns an handler.
		
		If distinct_until_changed=True, notifications will be emitted only on value changes.
		If distinct_until_changed=False, multiple spurious notifications will be emitted.
		
		To stop receiving the notifications, call .unregister() on the returned handler.
		Alternatively you can call .unregister(handler) on this client.
		'''
		self.assert_connected()
		
		self.logger.debug('registering callback for key state')
		cb = await self._create_callback_handler(Registers.KEY_STATE, user_callback, distinct_until_changed=distinct_until_changed)
		return cb
	
	
	async def notify_buttons(self, user_callback, distinct_until_changed=True):
		'''
		Subscribes to pressed buttons change notification.
		Requires a callback that accepts an integer representing the pressed buttons status from the Buttons enum:
			Buttons.NONE_PRESSED = 0x03
			Buttons.CENTRAL = 0x00
			Buttons.PLUS = 0x01
			Buttons.MINUS = 0x02
			
		Returns an handler.
		
		If distinct_until_changed=True, notifications will be emitted only on value changes.
		If distinct_until_changed=False, multiple spurious notifications will be emitted.
		
		To stop receiving the notifications, call .unregister() on the returned handler.
		Alternatively you can call .unregister(handler) on this client.
		'''
		self.assert_connected()
		
		self.logger.debug('registering callback for buttons')
		cb = await self._create_callback_handler(Registers.BUTTON, user_callback, distinct_until_changed=distinct_until_changed)
		return cb
	
	
	async def notify_rotation_speed(self, user_callback, distinct_until_changed=True):
		'''
		Subscribes to rotation speed change notification.
		Requires a callback that accepts an integer representing the rotation speed in rotations per second.
		Returns an handler.
		
		If distinct_until_changed=True, notifications will be emitted only on value changes.
		If distinct_until_changed=False, multiple spurious notifications will be emitted.
		
		To stop receiving the notifications, call .unregister() on the returned handler.
		Alternatively you can call .unregister(handler) on this client.
		'''
		self.assert_connected()
		
		self.logger.debug('registering callback for rotation speed')
		cb = await self._create_callback_handler(Registers.HALL, user_callback, distinct_until_changed=distinct_until_changed)
		return cb
	
	
	async def notify_depth(self, user_callback, distinct_until_changed=True):
		'''
		Subscribes to depth insertion change notification.
		Requires a callback that accepts an integer representing depth insertion from 0 to 8.
		Returns an handler.
		
		If distinct_until_changed=True, notifications will be emitted only on value changes.
		If distinct_until_changed=False, multiple spurious notifications will be emitted.
		
		To stop receiving the notifications, call .unregister() on the returned handler.
		Alternatively you can call .unregister(handler) on this client.
		'''
		self.assert_connected()
		
		self.logger.debug('registering callback for depth')
		cb = await self._create_callback_handler(Registers.LENGTH, user_callback, distinct_until_changed=distinct_until_changed)
		return cb
	
	
	async def notify_accelerometer(self, user_callback, distinct_until_changed=True):
		'''
		Subscribes to accelerometer data change notification.
		Requires a callback that accepts a touple of 3 integers (see get_accelerometers return value).
		Returns an handler.
		
		If distinct_until_changed=True, notifications will be emitted only on value changes.
		If distinct_until_changed=False, multiple spurious notifications will be emitted.
		
		To stop receiving the notifications, call .unregister() on the returned handler.
		Alternatively you can call .unregister(handler) on this client.
		'''
		self.assert_connected()
		
		self.logger.debug('registering callback for accelerometer')
		cb = await self._create_callback_handler(Registers.ACCELEROMETER, user_callback, distinct_until_changed=distinct_until_changed)
		return cb
	
	
	async def notify_temperature_and_pressure(self, user_callback, distinct_until_changed=True):
		'''
		Subscribes to temperature and pressure data change notification.
		Requires a callback that accepts a touple of 2 integers (see get_temperature_and_pressure return value).
		Returns an handler.
		
		If distinct_until_changed=True, notifications will be emitted only on value changes.
		If distinct_until_changed=False, multiple spurious notifications will be emitted.
		
		To stop receiving the notifications, call .unregister() on the returned handler.
		Alternatively you can call .unregister(handler) on this client.
		'''
		self.assert_connected()
		
		self.logger.debug('registering callback for pressure and temperature')
		cb = await self._create_callback_handler(Registers.PRESSURE_TEMPERATURE, user_callback, distinct_until_changed=distinct_until_changed)
		return cb
	
	
	@synchronized(SYNC_LOCK)
	async def _create_callback_handler(self, register, user_callback, distinct_until_changed=False):
		'''
		Internal use only.
		Creates a callback handler and registers BLE-level notification channel if needed.
		'''
		self.logger_callback.debug('creating callback handler for register %s %s', register.address, register.name)
		
		# Create the handler
		o = CallbackHandler(self, register, user_callback)

		if not register.address in self.user_handlers:
			self.user_handlers[register.address] = []
		registered_be_handlers = self.user_handlers[register.address]
		registered_be_handlers.append(o)
		
		self.logger_callback.debug('there are now %d callbacks listening for register %s %s', len(registered_be_handlers), register.address, register.name)

		# If this is the first callback for the characteristic, enable BLE notification channel
		if not register.address in self.bleak_handlers:
			self.logger_callback.debug('backend callback for register %s %s is not enabled (first listener), enabling now', register.address, register.name)
			def callback(sender, data):
				self._dispatch_notification(register, sender, data, distinct_until_changed=distinct_until_changed)

			self.bleak_handlers[register.address] = register.address
			await self.bleak_client.start_notify(register.address, callback)
			self.logger_callback.debug('registered backend callback for register %s %s', register.address, register.name)
			
		# Activate the handler before returning
		o.activate()
		
		self.logger_callback.info('activated user callback handler for register %s %s', register.address, register.name)
		return o


	def _dispatch_notification(self, register, sender, raw_data, distinct_until_changed=False):
		'''
		Internal use only.
		Dispatch notification to user callbacks.
		'''
		if distinct_until_changed:
			if not self._has_changed(register, raw_data):
				return

		self.logger_callback.debug('received notification of data change for register %s %s', register.address, register.name)
		converted = register.from_device(raw_data)
		self.logger_io.debug('NOTIFICATION %s %s >> %s', register.address, register.name, converted)
			
		if register.address in self.user_handlers and len(self.user_handlers[register.address]) > 0:
			for user_handler in self.user_handlers[register.address]:
				if user_handler.is_active():
					self.logger_callback.debug('dispatching notification of data change to user callback')
					user_handler.dispatch(converted)
				else:
					self.logger_callback.debug('skipping notification of data change to user callback because it is not active')
		else:
			self.logger_callback.warning('received notification from register %s but no user callbacks', register.address)


	def _has_changed(self, register, raw_data):
		'''
		Internal use only.
		Checks if register data has changed since last notification.
		Note: this method is long and branched because it is called a lot of times and needs to run faster.
		'''
		changed = False
		# self.logger_callback.debug('checking if data changed')
		
		if not register.address in self.callback_data_history:
			changed = True
		else:
	
			data_prv = self.callback_data_history[register.address]
			data_now_none = raw_data is None or len(raw_data) < 1
			data_prv_none = data_prv is None or len(data_prv) < 1
			
			if data_now_none and data_prv_none:
				return False
			elif not data_now_none and data_prv_none:
				changed = True
			elif data_now_none and not data_prv_none:
				changed = True
			elif len(raw_data) != len(data_prv):
				changed = True
			else:
				len_now = len(raw_data)
				i = 0
				while i < len_now:
					if raw_data[i] != data_prv[i]:
						changed = True
						break
					i = i + 1
			
		if changed:
			self.callback_data_history[register.address] = raw_data

		# self.logger_callback.debug('checking data changed resulted %s', changed)
		return changed


	@synchronized(SYNC_LOCK)
	async def unregister(self, callback_handler):
		'''
		Unregisters a callback handler and unregisters BLE-level notification channel if no longer needed.
		'''
		await self._unregister(callback_handler)
		

	async def _unregister(self, callback_handler):
		'''
		Internal use only.
		Unregisters a callback handler and unregisters BLE-level notification channel if no longer needed.
		'''
		if not callback_handler:
			raise ValueError('Callback handler to unregister is required')
		
		# Deactivate the handler
		callback_handler.deactivate()
		
		register = callback_handler.register
		self.logger_callback.debug('unregistering callback handler for register %s %s', register.address, register.name)
		callback_handler.deactivate()
		
		registered_be_handlers = self.user_handlers[register.address]
		registered_be_handlers.remove(callback_handler)
		
		self.logger_callback.debug('there are now %d callbacks listening for register %s %s', len(registered_be_handlers), register.address, register.name)
	
		# If this was the last callback for the characteristic, disable BLE notification channel
		if len(registered_be_handlers) < 1 and register.address in self.bleak_handlers:
			self.logger_callback.debug('backend callback for register %s %s is no longer needed, unregistering', register.address, register.name)
			
			self.bleak_handlers[register.address] = register.address
			await self.bleak_client.stop_notify(register.address)
			del self.bleak_handlers[register.address]
			self.logger_callback.debug('unregistered backend callback for register %s %s', register.address, register.name)

		self.logger_callback.info('deactivated user callback handler for register %s %s', register.address, register.name)