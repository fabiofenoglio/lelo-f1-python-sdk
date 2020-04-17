import asyncio
import time
import logging
import socket
import json


from .async_client import *


class SocketClient(AsyncClient):
	'''
	Asynchronous LELO F1 SDK SOCKET client.
	Configurable with standard logging.
	'''
	SOCKET_ENCODING = 'utf8'

	def __init__(self, ip_address, port):
		'''
		Instantiate the client. Takes ip_address as string and port as integer
		'''
		self.logger.debug('instantiating LELO F1 SDK SOCKET client')
		self.adapter = None
		
		self.remote_address = ip_address
		self.remote_port = port
		self.socket = None
		

	async def discover(self, timeout=1, address=None):
		raise ValueError('DISCOVER is not supported on socket client')


	async def connect(self):
		'''
		Connects to device with given ip_address and port.
		The 'timeout' parameter specifices maximum time before giving up.
		'''
		if not self.remote_address or not self.remote_port:
			raise ValueError('Address is required. Please provide ip_address and port')
		
		self.logger.info('attempting connection to %s:%d', self.remote_address, self.remote_port)
		
		try:
			self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.socket.connect((self.remote_address, self.remote_port))
			
			self.logger.info('succesfully connected to %s:%d', self.remote_address, self.remote_port)
			self.connected = True
			self.connected_address = self.remote_address + ':' + str(self.remote_port)
		
		except Exception as e:
			self.logger.exception('connection attempt failed: %s', e)
			self.connected = False
			raise e


		# Pings (reading a DeviceInfo register) to verify communication
		self.logger.debug('verifying communication layer')
		await self.ping()

		return self.socket
	
	
	async def disconnect(self):
		'''
		Disconnects from device.
		'''
		if not self.connected:
			self.logger.warning('client is not connected')
			return
		
		await self._disconnect()
	
	
	async def shutdown(self):
		'''
		Shutdown the device and disconnects.
		Automatically cancels pending notifications.
		'''
		await self.assert_authorized()

		self.logger.info('stopping motors')
		await self.stop_motors()
		
		await self._disconnect()


	async def _disconnect(self):
		self.logger.info('disconnecting from device')

		self.socket.close()

		self.connected = False
		self.socket = None
		self.connected_address = None

		self.logger.info('disconnected from device')


	async def is_authorized(self):
		'''
		Checks wether the user has authorized the connection by pressing the central button
		'''
		return self.is_connected() and (await self.get_remote_authorization() == True) and await self.get_key_state(silent=True)


	async def is_connection_authorized(self):
		'''
		Checks wether the user has authorized the connection by pressing the central button
		'''
		return self.is_connected() and (await self.get_remote_authorization() == True)


	async def is_remote_connected(self):
		'''
		Checks wether the user has authorized the connection by pressing the central button
		'''
		return self.is_connected() and await self.get_remote_connected()


	async def get_remote_authorization(self):
		'''
		Checks if remote server has authorized this client connection.
		'''
		return await self.send_command('authorized')


	async def get_remote_connected(self):
		'''
		Checks if remote server has connected to device.
		'''
		return await self.send_command('connected')


	async def request_remote_authorization(self):
		'''
		Prompts the server for authorization.
		'''
		return await self.send_command('authorize')


	async def send_command(self, command, arguments=None):
		'''
		Sends a command to remote socket.
		Handles JSON serialization/deserialization
		'''
		self.assert_connected()

		payload = dict()
		payload['command'] = command
		if arguments is not None:
			payload['arguments'] = arguments
		
		payload_str = json.dumps(payload)
		
		self.logger_io.debug('SEND %s', payload_str)
		
		self.socket.send(payload_str.encode(self.SOCKET_ENCODING))
		raw_response = self.socket.recv(1023).decode(self.SOCKET_ENCODING)
		
		self.logger_io.debug('RECEIVED %s', raw_response)
		
		response = json.loads(raw_response)

		if response and 'status' in response:
			if response['status'] == 'OK':
				return response['data'] if 'data' in response else None
			else:
				msg = response['status'] + ' - ' + (response['message'] if 'message' in response else 'generic error')
				self.logger_io.error('Response KO: %s - %s', raw_response, msg)
				raise ValueError(msg)
		else:
			self.logger_io.error('Malformed response: %s', raw_response)
			raise ValueError('Malformed response')
		

	async def assert_authorized(self):
		'''
		Shortcut method to raise error if the connection has not been authorized by pressing the central button
		'''
		if not await self.is_authorized():
			raise ValueError('Client is not authorized. Remote user should explicitly authorize you.')


	async def set_name(self, name):
		'''
		Sets the client name.
		'''
		return await self.send_command('name', [name])


	async def get_manufacturer_name(self):
		'''
		Reads the manufacturer name.
		Returns an ASCII UTF-8 string
		'''
		return await self.send_command('get_manufacturer_name')


	async def get_model_number(self):
		'''
		Reads the model number.
		Returns an ASCII UTF-8 string
		'''
		return await self.send_command('get_model_number')


	async def get_hardware_revision(self):
		'''
		Reads the device hardware revision.
		Returns an ASCII UTF-8 string
		'''
		return await self.send_command('get_hardware_revision')


	async def get_firmware_revision(self):
		'''
		Reads the device firmware revision.
		Returns an ASCII UTF-8 string
		'''
		return await self.send_command('get_firmware_revision')


	async def get_software_revision(self):
		'''
		Reads the device software revision.
		Returns an ASCII UTF-8 string
		'''
		return await self.send_command('get_software_revision')


	async def get_mac_address(self):
		'''
		Reads the device mac address.
		Returns an ASCII UTF-8 string in the format AA:BB:CC:DD:EE:FF
		'''
		return await self.send_command('get_mac_address')


	async def get_serial_number(self):
		'''
		Reads the device serial number.
		Returns an ASCII UTF-8 string in the format XX:......:YY
		'''
		return await self.send_command('get_serial_number')


	async def get_chip_id(self):
		'''
		Reads the device CHIP ID.
		Returns an ASCII UTF-8 string in the format XX:......:YY
		'''
		return await self.send_command('get_chip_id')


	async def get_device_name(self):
		'''
		Reads the device name.
		Returns an ASCII UTF-8 string
		'''
		return await self.send_command('get_device_name')


	async def get_system_id(self):
		'''
		Reads the system id.
		Returns an ASCII UTF-8 string in the format XX:......:YY
		'''
		return await self.send_command('get_system_id')


	async def get_pnp_id(self):
		'''
		Reads the PNP id.
		Returns an ASCII UTF-8 string in the format XX:......:YY
		'''
		return await self.send_command('get_pnp_id')


	async def get_ieee_11073_20601(self):
		'''
		Reads the IEEE 11073 20601 regulation mandatory specification.
		Returns an ASCII UTF-8 string in the format XX:......:YY
		'''
		return await self.send_command('get_ieee_11073_20601')


	async def get_battery_level(self):
		'''
		Reads the battery level.
		Returns an integer from 0 to 100
		'''
		return await self.send_command('get_battery_level')


	async def get_use_count(self):
		'''
		Reads the use count.
		Returns an integer.
		'''
		# await self.assert_authorized()
		return await self.send_command('get_use_count')


	async def reset_use_count(self):
		'''
		Resets device use count to zero.
		'''
		# await self.assert_authorized()
		self.logger.debug('resetting use count')
		return await self.send_command('reset_use_count')


	async def get_buttons_status(self):
		'''
		Reads the button status. 
		Returns an int value from the enum Buttons:
			Buttons.NONE_PRESSED = 0x03
			Buttons.CENTRAL = 0x00
			Buttons.PLUS = 0x01
			Buttons.MINUS = 0x02
		'''
		# await self.assert_authorized()
		return await self.send_command('get_buttons_status')


	async def get_temperature_and_pressure(self):
		'''
		Reads the device internal temperature and pressure.
		Returns a touple (temperature, pressure).
		Temperature is a floating point number with 2 decimals in Celsius degrees.
		Pressure is a floating point number with 2 decimals in mbar.
		Eg. (24.25, 987.23)
		'''
		# await self.assert_authorized()
		return await self.send_command('get_temperature_and_pressure')


	async def get_temperature(self):
		'''
		Reads the device internal temperature.
		Returns a floating point number with 2 decimals in Celsius degrees.
		Eg. (24.25, 987.23)
		'''
		# await self.assert_authorized()
		return await self.send_command('get_temperature')


	async def get_pressure(self):
		'''
		Reads the device internal pressure.
		Returns a floating point number with 2 decimals in mbar.
		Eg. 987.23
		'''
		# await self.assert_authorized()
		return await self.send_command('get_pressure')


	async def get_accelerometer(self):
		'''
		Reads the device accelerometer data.
		Returns a touple (x, y, z) where x, y and z are integers.
		Eg. (10, 200, 1000)
		'''
		# await self.assert_authorized()
		return await self.send_command('get_accelerometer')


	async def get_accelerometer_x(self):
		'''
		Reads the device accelerometer data for X axis.
		Returns an integer.
		'''
		# await self.assert_authorized()
		return await self.send_command('get_accelerometer_x')


	async def get_accelerometer_y(self):
		'''
		Reads the device accelerometer data for Y axis.
		Returns an integer.
		'''
		# await self.assert_authorized()
		return await self.send_command('get_accelerometer_y')


	async def get_accelerometer_z(self):
		'''
		Reads the device accelerometer data for Z axis.
		Returns an integer.
		'''
		# await self.assert_authorized()
		return await self.send_command('get_accelerometer_z')


	async def get_depth(self):
		'''
		Reads the insertion depth level.
		Returns an integer from 0 to 8.
		'''
		# await self.assert_authorized()
		return await self.send_command('get_depth')


	async def get_rotation_speed(self):
		'''
		Reads the rotation speed from Hall sensors.
		Returns an integer representing the rotations per second.
		'''
		# await self.assert_authorized()
		return await self.send_command('get_rotation_speed')


	async def get_wake_up(self):
		'''
		Reads the quick wake-up status.
		Returns a boolean.
		'''
		# await self.assert_authorized()
		return await self.send_command('get_wake_up')


	async def enable_wake_up(self):
		'''
		Enables quick wake-up.
		'''
		# await self.assert_authorized()
		self.logger.info('setting wake-up to %s', value)
		return await self.send_command('enable_wake_up')


	async def disable_wake_up(self):
		'''
		Disables quick wake-up.
		'''
		# await self.assert_authorized()
		self.logger.info('setting wake-up to %s', value)
		return await self.send_command('disable_wake_up')


	async def get_vibration_setting(self):
		'''
		Reads the device auto vibration settings
		Returns a touple of 8 integers ranging from 0 to 100.
		'''
		# await self.assert_authorized()
		return await self.send_command('get_vibration_setting')


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
		
		# await self.assert_authorized()
		self.logger.info('setting vibration-setting to %s', value)
		return await self.send_command('set_vibration_setting', [value])


	async def get_cruise_control(self):
		'''
		Reads the cruise control status.
		Returns a boolean.
		'''
		# await self.assert_authorized()
		return await self.send_command('get_cruise_control')


	async def disable_cruise_control(self):
		'''
		Disables cruise control.
		'''
		# await self.assert_authorized()
		return await self.send_command('disable_cruise_control')


	async def enable_cruise_control(self, reset=False):
		'''
		Enables cruise control.
		If reset=True is passed, resets motors speed to default value.
		'''
		# await self.assert_authorized()
		return await self.send_command('enable_cruise_control', [reset])


	async def get_key_state(self, silent=False):
		'''
		Reads the key state status.
		Returns a boolean.
		'''		
		self.assert_connected()
		if not silent:
			self.logger.debug('checking key state')
		return await self.send_command('get_key_state')


	async def stop_motors(self):
		'''
		Stops both motors of the device.
		'''
		# await self.assert_authorized()
		
		self.logger.info('sending motors stop signal')
		return await self.send_command('stop_motors')


	async def verify_accelerometer(self):
		'''
		Puts the device into VERIFY ACCELEROMETER mode.
		'''
		# await self.assert_authorized()
		self.logger.info('enterying accelerometer verification mode')
		return await self.send_command('verify_accelerometer')
	
	
	async def get_motors_speed(self):
		'''
		Reads the two motors speed.
		Returns a touple (X, Y) with X being the main motor speed ranging from 0 to 100
		and Y being the vibrator motor speed ranging from 0 to 100
		'''
		# await self.assert_authorized()
		return await self.send_command('get_motors_speed')


	async def get_main_motor_speed(self):
		'''
		Reads the main motor speed.
		Returns an integer ranging from 0 to 100
		'''
		# await self.assert_authorized()
		return await self.send_command('get_main_motor_speed')


	async def get_vibration_speed(self):
		'''
		Reads the vibrator motor speed.
		Returns an integer ranging from 0 to 100
		'''
		# await self.assert_authorized()
		return await self.send_command('get_vibration_speed')


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
		
		# await self.assert_authorized()
		self.logger.info('setting motor speed to %d and vibration speed to %d', value[0], value[1])
		return await self.send_command('set_motors_speed', [value])


	async def set_main_motor_speed(self, value):
		'''
		Sets the main motor speed.
		Takes an integer ranging from 0 to 100
		'''
		if value is None:
			raise ValueError('Value is required')
		if value < 0 or value > 100:
			raise ValueError('Value should be between 0 and 100')
		
		# await self.assert_authorized()
		self.logger.info('setting main motor speed to %d', value)
		return await self.send_command('set_main_motor_speed', [value])


	async def set_vibration_speed(self, value):
		'''
		Sets the vibrator motor speed.
		Takes an integer ranging from 0 to 100
		'''
		if value is None:
			raise ValueError('Value is required')
		if value < 0 or value > 100:
			raise ValueError('Value should be between 0 and 100')
		
		# await self.assert_authorized()
		self.logger.info('setting vibration speed to %d', value)
		return await self.send_command('set_vibration_speed', [value])


	async def ping(self):
		'''
		Reads from a register to test device communication
		'''
		self.assert_connected()

		self.logger.debug('sending ping to device')
		await self.send_command('ping')
		self.logger.debug('device responded to ping')
	

	async def read(self, register, silent=False): self.not_supported()
	async def write(self, register, value=None): self.not_supported()
	async def notify_key_state(self, user_callback, distinct_until_changed=True): self.not_supported()
	async def notify_buttons(self, user_callback, distinct_until_changed=True): self.not_supported()
	async def notify_rotation_speed(self, user_callback, distinct_until_changed=True): self.not_supported()
	async def notify_depth(self, user_callback, distinct_until_changed=True): self.not_supported()
	async def notify_accelerometer(self, user_callback, distinct_until_changed=True): self.not_supported()
	async def notify_temperature_and_pressure(self, user_callback, distinct_until_changed=True): self.not_supported()
	async def _create_callback_handler(self, register, user_callback, distinct_until_changed=False): self.not_supported()
	def _dispatch_notification(self, register, sender, raw_data, distinct_until_changed=False): self.not_supported()
	async def unregister(self, callback_handler): self.not_supported()
	async def _unregister(self, callback_handler): self.not_supported()
	async def _shutdown_notifications(self): self.not_supported()
	
	def not_supported(self):
		raise ValueError('Not supported on socket client')