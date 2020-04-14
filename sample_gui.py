import asyncio
import logging
import threading
import PySimpleGUI as sg
from collections.abc import Sequence

import lelof1py as f1client


# Configure logging to a basic level
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Configure logging for the library
logging.getLogger(f1client.Constants.LOGGER_NAME).setLevel(logging.INFO)
logging.getLogger(f1client.Constants.LOGGER_IO_NAME).setLevel(logging.WARN)
logging.getLogger(f1client.Constants.LOGGER_CALLBACK_NAME).setLevel(logging.INFO)

# Configure logging for the backend BLE adapter (bleak)
logging.getLogger('bleak').setLevel(logging.INFO)


# Initialize context with service
class GUISample:
	'''
	Complete sample of device discovery, connection and control with simple GUI 
	'''
	
	# Actions for the GUI
	FIELD_STATUS = 'status'
	FIELD_LOG = 'log'
	FIELD_DEVICE = 'device'
	FIELD_BUTTONS = 'buttons'
	FIELD_BATTERY = 'battery'
	FIELD_KEY_STATE = 'key_state'
	FIELD_ACCELEROMETER = 'acceleration'
	FIELD_PRESSURE = 'pressure'
	FIELD_TEMPERATURE = 'temperature'
	FIELD_ROTATION_SPEED = 'hall'
	FIELD_DEPTH = 'depth'
	FIELD_USE_LOG = 'use_log'
	FIELD_WAKE_UP = 'wake_up'
	FIELD_CRUISE_CONTROL = 'cruise_control'
	FIELD_VIBRATOR_SETTINGS = 'vib_settings'
	FIELD_MAIN_MOTOR = 'main_motor'
	FIELD_VIBRATOR_MOTOR = 'vib_motor'
	
	EVENT_DISCOVER = 'discover'
	EVENT_EXIT = 'exit'
	EVENT_CONNECT = 'connect'
	EVENT_DISCONNECT = 'disconnect'
	EVENT_RESET_USE_COUNT = 'reset_use_count'
	EVENT_MAIN_MOTOR_PLUS = 'mm_plus'
	EVENT_MAIN_MOTOR_MINUS = 'mm_minus'
	EVENT_MAIN_MOTOR_OFF = 'mm_off'
	EVENT_VIB_MOTOR_PLUS = 'vm_plus'
	EVENT_VIB_MOTOR_MINUS = 'vm_minus'
	EVENT_VIB_MOTOR_OFF = 'vm_off'
	

	def __init__(self, loop, refresh_interval=1/100):
		'''
		Initializes the window and prepares the layout
		'''
		self.loop = loop
			
		# initialize F1 client
		self.client = f1client.AsyncClient()
	
		# Discovered devices
		self.devices = []
		
		# Set GUI theme
		sg.theme('Dark Blue 3')
		
		# Initialize window
		self.window = sg.Window('LELO F1 SDK Python example', [
			[sg.Frame('Status', [
					[sg.Text('Status:'), sg.Text('initializing ...', size=(50,1), key=self.FIELD_STATUS)],
					[sg.Text('Device:'), sg.Text('', size=(50,1), key=self.FIELD_DEVICE)],
					[sg.Text('Key state:'), sg.Text('', size=(30,1), key=self.FIELD_KEY_STATE)],
					[sg.Text('Use count:'), sg.Text('', size=(44,1), key=self.FIELD_USE_LOG),
					 sg.Button('reset', key=self.EVENT_RESET_USE_COUNT)
					],
					[sg.Text('', pad=((0, 0), (0, 10)))],
					[sg.Button('Discover', key=self.EVENT_DISCOVER), 
					 sg.Button('Connect', key=self.EVENT_CONNECT, disabled=True), 
					 sg.Button('Disconnect', key=self.EVENT_DISCONNECT, disabled=True)]
				], pad=(5,10)),
			 sg.Frame('Settings', [
					[sg.Text('Quick wake-up:'), sg.Text('', size=(50,1), key=self.FIELD_WAKE_UP)],
					[sg.Text('Cruise control:'), sg.Text('', size=(50,1), key=self.FIELD_CRUISE_CONTROL)],
					[sg.Text('Auto vibrator settings:'), sg.Text('', size=(50,1), key=self.FIELD_VIBRATOR_SETTINGS)],
					[sg.Text('', pad=((0, 0), (0, 10)))],
					[sg.Text('Main motor:'), sg.ProgressBar(100, orientation='h', size=(25, 20), key=self.FIELD_MAIN_MOTOR, pad=((16, 0), (0, 0))),
					 sg.Button('off', key=self.EVENT_MAIN_MOTOR_OFF, size=(5, None)), 
					 sg.Button('-', key=self.EVENT_MAIN_MOTOR_MINUS, size=(5, None)),
					 sg.Button('+', key=self.EVENT_MAIN_MOTOR_PLUS, size=(5, None))],
					[sg.Text('Vibrator motor:'), sg.ProgressBar(100, orientation='h', size=(25, 20), key=self.FIELD_VIBRATOR_MOTOR, pad=(1,0)),
					 sg.Button('off', key=self.EVENT_VIB_MOTOR_OFF, size=(5, None)), 
					 sg.Button('-', key=self.EVENT_VIB_MOTOR_MINUS, size=(5, None)),
					 sg.Button('+', key=self.EVENT_VIB_MOTOR_PLUS, size=(5, None))]
				], pad=(5,10))
			],
			[sg.Multiline('initializing', size=(68,13), disabled=True, key=self.FIELD_LOG, pad=(5,5)),
			 sg.Frame('Sensors', [
				[sg.Text('Buttons:'), sg.Text('no buttons pressed', size=(30,1), key=self.FIELD_BUTTONS)],
				[sg.Text('Accelerometer:'), sg.Text('', size=(54,1), key=self.FIELD_ACCELEROMETER)],
				[sg.Text('Temperature:'), sg.Text('', size=(50,1), key=self.FIELD_TEMPERATURE)],
				[sg.Text('Pressure:'), sg.Text('', size=(50,1), key=self.FIELD_PRESSURE)],
				[sg.Text('Rotation speed:'), sg.Text('', size=(50,1), key=self.FIELD_ROTATION_SPEED)],
				[sg.Text('Depth:'), sg.Text('', size=(50,1), key=self.FIELD_DEPTH)],
				[sg.Text('Battery:'), sg.ProgressBar(100, orientation='h', size=(44, 20), key=self.FIELD_BATTERY)],
			], pad=(5,10))],
			
			[sg.Button('Exit', key=self.EVENT_EXIT)]

		], finalize=True)
		
		# Schedules tasks in execution order: 
		# first discover routine, window refresh task and battery level update task
		self.tasks = []
		self.schedule(self.discover())
		self.tasks.append(loop.create_task(self.updater(refresh_interval)))
		self.tasks.append(loop.create_task(self.battery_level_updater(5)))


	def log(self, line):
		'''
		Appends a line to the multiline control and autoscrolls to the end
		forces instant window refresh
		'''
		self.window[self.FIELD_LOG].update('\n' + str(line), append=True, autoscroll=True)
		logging.info(line)
	
	
	def update_status(self, status):
		'''
		Updates the status label and adds a line to the log control
		'''
		self.log(status)
		self.update(self.FIELD_STATUS, status)


	def lock(self):
		'''
		Lock all buttons to avoid user launching concurrent operations
		while some operation is in progress
		'''
		self.window[self.EVENT_EXIT].update(disabled=True)
		self.window[self.EVENT_DISCOVER].update(disabled=True)
		self.window[self.EVENT_CONNECT].update(disabled=True)
		self.window[self.EVENT_DISCONNECT].update(disabled=True)
		self.window[self.EVENT_RESET_USE_COUNT].update(disabled=True)
		self.window[self.EVENT_MAIN_MOTOR_PLUS].update(disabled=True)
		self.window[self.EVENT_MAIN_MOTOR_MINUS].update(disabled=True)
		self.window[self.EVENT_MAIN_MOTOR_OFF].update(disabled=True)
		self.window[self.EVENT_VIB_MOTOR_PLUS].update(disabled=True)
		self.window[self.EVENT_VIB_MOTOR_MINUS].update(disabled=True)
		self.window[self.EVENT_VIB_MOTOR_OFF].update(disabled=True)
		
	
	async def unlock(self):
		'''
		Unlock buttons based on application status
		'''
		self.window[self.EVENT_DISCOVER].update(disabled=False)
		self.window[self.EVENT_EXIT].update(disabled=False)

		connected = self.client and self.client.is_connected()
		
		if connected:
			self.window[self.EVENT_DISCONNECT].update(disabled=False)
			
			authorized = await self.client.is_authorized()
			if authorized:
				self.window[self.EVENT_RESET_USE_COUNT].update(disabled=False)
				self.window[self.EVENT_MAIN_MOTOR_PLUS].update(disabled=False)
				self.window[self.EVENT_MAIN_MOTOR_MINUS].update(disabled=False)
				self.window[self.EVENT_MAIN_MOTOR_OFF].update(disabled=False)
				self.window[self.EVENT_VIB_MOTOR_PLUS].update(disabled=False)
				self.window[self.EVENT_VIB_MOTOR_MINUS].update(disabled=False)
				self.window[self.EVENT_VIB_MOTOR_OFF].update(disabled=False)
			
		else:
			if self.devices:
				self.window[self.EVENT_CONNECT].update(disabled=False)
		

	def update(self, field, val):
		'''
		Shortcut to update a control text and force window refresh
		'''
		self.window[field].update(val)
		self.window.refresh()


	async def discover(self):
		'''
		Launch device discovery.
		Looks for devices with name = 'F1s'.
		
		You can specify the timeout as argument of the discover() method
		'''
		if not self.client:
			self.client = f1client.AsyncClient()

		self.update_status('searching for device ...')

		self.devices = await self.client.discover(timeout=60)
		if self.devices:
			self.update_status('device found: ' + self.devices[0].address)
		else:
			self.update_status('no device found')


	async def connect(self):
		'''
		Attempts connection to the first discovered device
		
		You can specify the timeout as argument of the discover() method.
		Once connected, waits for authorization (user should press the central button).
		Once authorized, stops the motors and returns. 
		'''
		if not self.client:
			self.client = f1client.AsyncClient()

		self.update_status('connecting to device ...')

		await self.client.connect(self.devices[0].address, timeout=30)
		self.update_status('waiting for authorization. PRESS THE CENTRAL BUTTON')

		while not await self.client.get_key_state():
			await asyncio.sleep(1)
		
		await self.client.stop_motors()
		self.update_status('connected to device')
		
		# Read device info
		await self.refresh_status()

		# Register for BLE notifications
		await self.subscribe_notifications()

	
	async def subscribe_notifications(self):
		'''
		Subscribres to device push notifications to avoid an intensive and 
		battery-consuming polling
		'''
		await self.client.notify_buttons(self.buttons_changed)
		await self.client.notify_key_state(self.key_state_changed)
		await self.client.notify_rotation_speed(self.rotation_speed_changed)
		await self.client.notify_depth(self.depth_changed)
		await self.client.notify_accelerometer(self.accelerometer_changed)
		await self.client.notify_temperature_and_pressure(self.temperature_and_pressure_changed)


	async def disconnect(self):
		'''
		Disconnects from device. 
		If device is connected and authorization has been gived, the device is shutdown.
		'''
		self.update_status('disconnecting from device')

		if self.client.is_connected():
			if await self.client.is_authorized():
				self.update_status('shutting down device')
				await self.client.shutdown()
			self.update_status('closing connection')
			await self.client.disconnect()

		self.update_status('device disconnected')
		self.update(self.FIELD_DEVICE, 'no device')
		self.window[self.FIELD_BATTERY].update_bar(0)

		self.client = None
		
	
	async def assert_authorized(self):
		'''
		Checks that client is connected and that authorization buttons has been pressed
		'''
		if not self.client.is_connected() or not await self.client.is_authorized():
			self.log('client not connected or authorized')
			return False
		return True
	

	async def reset_use_count(self):
		'''
		Resets use count to zero
		'''
		self.log('clearing use count')
		await self.client.reset_use_count()
		self.log('use count cleared')
		await self.refresh_use_count()
		
	
	async def shutdown_main_motor(self):
		'''
		Shutdown the main motor
		'''
		self.log('setting main motor speed to 0 %')
		await self.client.set_main_motor_speed(0)
		await self.refresh_motors_speed()

	
	async def decrement_main_motor(self):
		'''
		Decrements the main motor speed. If less than 30, the motor is shutdown.
		'''
		actual = await self.client.get_main_motor_speed()
		if actual < 1:
			return

		to_set = actual - 5
		if (to_set < 30):
			to_set = 0
		
		self.log('setting main motor speed to ' + str(to_set) + ' %')
		
		await self.client.set_main_motor_speed(to_set)
		await self.refresh_motors_speed()

	
	async def increment_main_motor(self):
		'''
		Increments the main motor speed. If less than 30, the motor is set to 30 to combat inertia.
		'''
		actual = await self.client.get_main_motor_speed()
		if actual >= 100:
			return

		to_set = actual + 5
		if (to_set < 30):
			to_set = 30
		elif (to_set > 100):
			to_set = 100
		
		self.log('setting main motor speed to ' + str(to_set) + ' %')
		
		await self.client.set_main_motor_speed(to_set)
		await self.refresh_motors_speed()

	
	async def shutdown_vibe_motor(self):
		'''
		Shutdown the vibe motor
		'''
		self.log('setting vibe motor speed to 0 %')
		await self.client.set_vibration_speed(0)
		await self.refresh_motors_speed()
	
	
	async def decrement_vibe_motor(self):
		'''
		Decrements the vibrator motor speed. If less than 30, the motor is shutdown.
		'''
		actual = await self.client.get_vibration_speed()
		if actual < 1:
			return

		to_set = actual - 5
		if (to_set < 30):
			to_set = 0
		
		self.log('setting vibe motor speed to ' + str(to_set) + ' %')
		
		await self.client.set_vibration_speed(to_set)
		await self.refresh_motors_speed()

	
	async def increment_vibe_motor(self):
		'''
		Increments the vibrator motor speed. If less than 30, the motor is set to 30 to combat inertia.
		'''
		actual = await self.client.get_vibration_speed()
		if actual >= 100:
			return

		to_set = actual + 5
		if (to_set < 30):
			to_set = 30
		elif (to_set > 100):
			to_set = 100
		
		self.log('setting vibe motor speed to ' + str(to_set) + ' %')
		
		await self.client.set_vibration_speed(to_set)
		await self.refresh_motors_speed()


	def buttons_changed(self, button_status):
		'''
		Handle a button notification callback
		'''
		if button_status == f1client.Buttons.PLUS:
			text = 'PRESSED + BUTTON'
		elif button_status == f1client.Buttons.MINUS:
			text = 'PRESSED - BUTTON'
		elif button_status == f1client.Buttons.CENTRAL:
			text = 'PRESSED CENTRAL BUTTON'
		else:
			text = 'no buttons pressed'
	
		self.update(self.FIELD_BUTTONS, text)


	def key_state_changed(self, new_value):
		'''
		Handle a change of the key state (eg. user has pressed the central button)
		'''
		self.update(self.FIELD_KEY_STATE, 'authorized' if new_value else 'not authorized')
	
	
	def accelerometer_changed(self, new_value):
		'''
		Handle a change of the accelerometer data
		'''
		self.update(self.FIELD_ACCELEROMETER, 'X: ' + str(new_value[0]) + ' Y: ' + str(new_value[1]) + ' Z: ' + str(new_value[2]) )
	
	
	def temperature_and_pressure_changed(self, new_value):
		'''
		Handle a change in pressure or temperature data
		'''
		self.update(self.FIELD_TEMPERATURE, (str(new_value[0]) + ' C') if new_value[0] > 0 else '--' )
		self.update(self.FIELD_PRESSURE, (str(new_value[1]) + ' mbar') if new_value[1] > 0 else '--' )

	
	def rotation_speed_changed(self, new_value):
		'''
		Handle a change in detected motor speed via hall sensors
		'''
		self.update(self.FIELD_ROTATION_SPEED, str(new_value) + ' rpm')
	
	
	def depth_changed(self, new_value):
		'''
		Handle a change in detected penetration depth
		'''
		self.update(self.FIELD_DEPTH, str(new_value) + ' / 8')


	async def refresh_status(self):
		'''
		Refresh all static configuration of device, battery level and motors speed.
		Called once on device connection.
		'''
		
		# Read device identifiers
		self.update(self.FIELD_DEVICE,
			await self.client.get_manufacturer_name() + ' ' +
			await self.client.get_hardware_revision() + ' (' +
			await self.client.get_mac_address() + ')'
		)
		
		await self.refresh_use_count()
		
		# Check if quick wake-up is enabled
		self.update(self.FIELD_WAKE_UP, 'enabled' if await self.client.get_wake_up() else 'disabled')

		# Check if cruise control is enabled
		self.update(self.FIELD_CRUISE_CONTROL, 'enabled' if await self.client.get_cruise_control() else 'disabled')

		# Read auto vibrator levels
		self.update(self.FIELD_VIBRATOR_SETTINGS, ', '.join(str(level) for level in await self.client.get_vibration_setting()))
		
		await self.refresh_battery_level()
		await self.refresh_motors_speed()
		
		
	async def refresh_battery_level(self):
		'''
		Refresh battery level indication. 
		Called once on device connection and periodically.
		'''
		
		# Read battery status
		level = await self.client.get_battery_level()
		logging.info('current battery level is %d', level)
		
		self.window[self.FIELD_BATTERY].update_bar(level)
	

	async def refresh_use_count(self):
		'''
		Refresh use count.
		Called once on device connection.
		'''

		# Read use count
		self.update(self.FIELD_USE_LOG, str(await self.client.get_use_count()))
		
	
	async def refresh_motors_speed(self):
		'''
		Refresh motors speed. 
		Called once on device connection and on motors speed change.
		'''
		
		# Read motors speed
		motors_speed = await self.client.get_motors_speed()
		self.window[self.FIELD_MAIN_MOTOR].update_bar(motors_speed[0])
		self.window[self.FIELD_VIBRATOR_MOTOR].update_bar(motors_speed[1])


	def schedule(self, task, locking=True):
		'''
		Schedule a task for execution in asyncio event loop.
		Locks the button until the task has completed, then enables buttons depending on application state.
		'''
		async def runner(task):
			try:
				if locking: 
					self.lock()
				await task
			except Exception as e:
				logging.exception('error in task: %s', e)
				self.log('error in task: ' + str(e))
			finally:
				if locking: 
					await self.unlock()

		self.loop.create_task(runner(task))


	async def updater(self, interval):
		'''
		Main event loop. Runs inside asyncio event loop
		'''
		
		while True:
			try:
				self.window.refresh()
				event, values = self.window.read(timeout=10)
				
				if event is None or event == self.EVENT_EXIT:
					if self.client and self.client.is_connected():
						await self.disconnect()
					self.close()
					break
				elif event == self.EVENT_DISCOVER:
					self.schedule(self.discover())
				elif event == self.EVENT_CONNECT:
					self.schedule(self.connect())
				elif event == self.EVENT_DISCONNECT:
					self.schedule(self.disconnect())
				elif event == self.EVENT_RESET_USE_COUNT:
					self.schedule(self.reset_use_count())
				elif event == self.EVENT_MAIN_MOTOR_MINUS:
					self.schedule(self.decrement_main_motor())
				elif event == self.EVENT_MAIN_MOTOR_PLUS:
					self.schedule(self.increment_main_motor())
				elif event == self.EVENT_MAIN_MOTOR_OFF:
					self.schedule(self.shutdown_main_motor())
				elif event == self.EVENT_VIB_MOTOR_MINUS:
					self.schedule(self.decrement_vibe_motor())
				elif event == self.EVENT_VIB_MOTOR_PLUS:
					self.schedule(self.increment_vibe_motor())
				elif event == self.EVENT_VIB_MOTOR_OFF:
					self.schedule(self.shutdown_vibe_motor())
				
			except Exception as e:
				logging.error('error in updater task: %s', e)

			await asyncio.sleep(interval)


	async def battery_level_updater(self, interval):
		'''
		Battery level updater coroutine. Runs inside asyncio event loop
		'''
		while True:
			try:
				if self.client and self.client.is_connected():
					self.schedule(self.refresh_battery_level(), locking=False)
			except Exception as e:
				logging.error('error in battery_level_updater task: %s', e)

			await asyncio.sleep(interval)


	def close(self):
		'''
		Cancel all registered tasks and close window.
		'''
		self.window.close()
		for task in self.tasks:
			task.cancel()

		self.loop.stop()


# Run the sample in asyncio event loop
loop = asyncio.get_event_loop()
app = GUISample(loop)
loop.run_forever()
loop.close()
