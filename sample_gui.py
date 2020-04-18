import asyncio
import logging
import threading
import time
import PySimpleGUI as sg
from asyncio.futures import CancelledError

import lelof1py as f1client


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
		self.client = None
		self.locked = False
		self.stopped = False
		self.loop = loop
		self.snapshot = dict()
		self.fs_utils = f1client.FsUtils(self.__class__.__name__)
	
		# Discovered devices
		self.devices = []
		
		# Set GUI theme
		sg.theme('Dark Blue 3')
		
		# Initialize window
		self.window = sg.Window('LELO F1 SDK Python example', self.get_layout(), finalize=True)
		
		# Schedules tasks in execution order: 
		# first discover routine, window refresh task and battery level update task
		self.tasks = []
		self.schedule(self.post_construct(), name='post_construct')
		self.schedule(self.discover(autoconnect=True), name='discover_and_connect')
		self.tasks.append(loop.create_task(self.updater(refresh_interval)))
		self.tasks.append(loop.create_task(self.battery_level_updater(60)))


	def get_layout(self):
		
		return [
			[sg.Frame('Status', [
					[sg.Text('Status:'), sg.Text('initializing ...', size=(50,1), key=self.FIELD_STATUS)],
					[sg.Text('Device:'), sg.Text('--', size=(50,1), key=self.FIELD_DEVICE)],
					[sg.Text('Key state:'), sg.Text('not authorized', size=(30,1), key=self.FIELD_KEY_STATE)],
					[sg.Text('Use count:'), sg.Text('--', size=(44,1), key=self.FIELD_USE_LOG),
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

		]


	async def post_construct(self):
		'''
		Method to be overrided
		'''
		self.tasks.append(self.loop.create_task(self.sensor_status_updater(1)))


	def get_client(self):
		if not self.client:
			self.client = f1client.AsyncClient()
			
			# KEY_STATE is managed by application
			self.client.disable_key_state_check()
			
		return self.client


	async def is_connected(self):
		v = self.client and self.client.is_connected()
		self.snapshot['connected'] = v
		return v


	async def is_authorized(self):
		if 'authorized' in self.snapshot:
			return self.snapshot['authorized']
		else:
			v = self.client and await self.client.is_authorized()
			self.snapshot['authorized'] = v
			return v


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
		try:
			self.log(status)
			self.update(self.FIELD_STATUS, status)
			self.snapshot['status'] = status
		except Exception as e:
			logging.info('updating status: %s', status)
			logging.warn('error updating status: %s', e)


	def lock(self):
		'''
		Lock all buttons to avoid user launching concurrent operations
		while some operation is in progress
		'''
		self.locked = True 
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
		self.snapshot['locked'] = self.locked
	
	
	async def unlock(self):
		'''
		Unlock buttons based on application status
		'''
		self.window[self.EVENT_DISCOVER].update(disabled=False)
		self.window[self.EVENT_EXIT].update(disabled=False)

		connected = self.get_client() and await self.is_connected()
		
		if connected:
			self.window[self.EVENT_DISCONNECT].update(disabled=False)
			
			authorized = await self.is_authorized()
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

	
		self.locked = False
		self.snapshot['locked'] = self.locked


	def update(self, field, val):
		'''
		Shortcut to update a control text and force window refresh
		'''
		self.window[field].update(val)
		self.window.refresh()


	async def discover(self, autoconnect=False):
		'''
		Launch device discovery.
		Looks for devices with name = 'F1s'.
		
		You can specify the timeout as argument of the discover() method
		'''
		if autoconnect:
			last_profile = self.fs_utils.load_connection_profile(safe=True)
			if last_profile:
				self.update_status('attempting reconnection to last device (' + last_profile.address + ')')
				try:
					await self.connect(last_profile.address)
					return
				except Exception as e:
					self.update_status('reconnection to last device failed')

		self.update_status('searching for device ...')

		self.devices = await self.get_client().discover(timeout=60)
		if self.devices:
			self.update_status('device found: ' + self.devices[0].address)
			if autoconnect:
				logging.debug('attempting automatic connection ...')
				await self.connect()
		else:
			self.update_status('no device found')


	async def connect(self, addr=None):
		'''
		Attempts connection to the first discovered device
		
		You can specify the timeout as argument of the discover() method.
		Once connected, waits for authorization (user should press the central button).
		Once authorized, stops the motors and returns. 
		'''
		self.update_status('connecting to device ...')
		
		if not addr:
			addr = self.devices[0].address

		await self.get_client().connect(addr, timeout=30)
		self.update_status('waiting for authorization. PRESS THE CENTRAL BUTTON')

		while not await self.get_client().get_key_state():
			await asyncio.sleep(1)
		
		await self.get_client().stop_motors()
		self.update_status('connected to device')
		
		# Read device info
		await self.refresh_status()

		# Register for BLE notifications
		await self.subscribe_notifications()
		
		self.snapshot['connected'] = True
		self.snapshot['authorized'] = True
		
		profile = f1client.ConnectionProfile()
		profile.address = addr
		profile.uuid = 'not-supported (' + addr + ')'
		
		self.fs_utils.save_connection_profile(profile, safe=True)

	
	async def subscribe_notifications(self):
		'''
		Subscribres to device push notifications to avoid an intensive and 
		battery-consuming polling
		'''
		await self.get_client().notify_buttons(self.buttons_changed)
		await self.get_client().notify_key_state(self.key_state_changed)
		await self.get_client().notify_rotation_speed(self.rotation_speed_changed)
		await self.get_client().notify_depth(self.depth_changed)
		await self.get_client().notify_accelerometer(self.accelerometer_changed)
		await self.get_client().notify_temperature_and_pressure(self.temperature_and_pressure_changed)
		

	async def disconnect(self):
		'''
		Disconnects from device. 
		If device is connected and authorization has been gived, the device is shutdown.
		'''
		self.update_status('disconnecting from device')

		if await self.is_connected():
			if await self.is_authorized():
				self.update_status('shutting down device')
				await self.get_client().shutdown()
			self.update_status('closing connection')
			await self.get_client().disconnect()

		self.update_status('device disconnected')
		self.update(self.FIELD_DEVICE, 'no device')
		self.window[self.FIELD_BATTERY].update_bar(0)

		self.client = None
		self.snapshot['connected'] = False

	
	async def assert_authorized(self):
		'''
		Checks that client is connected and that authorization buttons has been pressed
		'''
		if not await self.is_connected() or not await self.is_authorized():
			self.log('client not connected or authorized')
			return False
		return True
	

	async def reset_use_count(self):
		'''
		Resets use count to zero
		'''
		self.log('clearing use count')
		await self.get_client().reset_use_count()
		self.log('use count cleared')
		await self.refresh_use_count()
	
	
	async def get_main_motor_speed(self):
		if 'main_motor' in self.snapshot:
			logging.debug('reusing cached main motor speed')
			return self.snapshot['main_motor']
		else:
			logging.debug('reading main motor speed from device')
			return await self.get_client().get_main_motor_speed()
	

	async def get_vibration_speed(self):
		if 'vibe_motor' in self.snapshot:
			logging.debug('reusing cached vibe motor speed')
			return self.snapshot['vibe_motor']
		else:
			logging.debug('reading vibe motor speed from device')
			return await self.get_client().get_vibration_speed()
	

	async def shutdown_main_motor(self):
		'''
		Shutdown the main motor
		'''
		self.log('setting main motor speed to 0 %')
		
		self.snapshot['main_motor'] = 0
		
		await self.get_client().set_motors_speed([0, await self.get_vibration_speed()])
		self.window[self.FIELD_MAIN_MOTOR].update_bar(0)

	
	async def decrement_main_motor(self):
		'''
		Decrements the main motor speed. If less than 30, the motor is shutdown.
		'''
		actual = await self.get_main_motor_speed()
		if actual < 1:
			return

		to_set = actual - 5
		if (to_set < 30):
			to_set = 0
		
		self.log('setting main motor speed to ' + str(to_set) + ' %')
		
		self.snapshot['main_motor'] = to_set
		await self.get_client().set_motors_speed([to_set, await self.get_vibration_speed()])
		self.window[self.FIELD_MAIN_MOTOR].update_bar(to_set)


	async def increment_main_motor(self):
		'''
		Increments the main motor speed. If less than 30, the motor is set to 30 to combat inertia.
		'''
		actual = await self.get_main_motor_speed()
		if actual >= 100:
			return

		to_set = actual + 5
		if (to_set < 30):
			to_set = 30
		elif (to_set > 100):
			to_set = 100
		
		self.log('setting main motor speed to ' + str(to_set) + ' %')
		
		self.snapshot['main_motor'] = to_set
		await self.get_client().set_motors_speed([to_set, await self.get_vibration_speed()])
		self.window[self.FIELD_MAIN_MOTOR].update_bar(to_set)

	
	async def shutdown_vibe_motor(self):
		'''
		Shutdown the vibe motor
		'''
		self.log('setting vibe motor speed to 0 %')
		
		self.snapshot['vibe_motor'] = 0
		await self.get_client().set_motors_speed([await self.get_main_motor_speed(), 0])
		self.window[self.FIELD_VIBRATOR_MOTOR].update_bar(0)
	
	
	async def decrement_vibe_motor(self):
		'''
		Decrements the vibrator motor speed. If less than 30, the motor is shutdown.
		'''
		actual = await self.get_vibration_speed()
		if actual < 1:
			return

		to_set = actual - 5
		if (to_set < 30):
			to_set = 0
		
		self.log('setting vibe motor speed to ' + str(to_set) + ' %')
		
		self.snapshot['vibe_motor'] = to_set
		await self.get_client().set_motors_speed([await self.get_main_motor_speed(), to_set])
		self.window[self.FIELD_VIBRATOR_MOTOR].update_bar(to_set)

	
	async def increment_vibe_motor(self):
		'''
		Increments the vibrator motor speed. If less than 30, the motor is set to 30 to combat inertia.
		'''
		actual = await self.get_vibration_speed()
		if actual >= 100:
			return

		to_set = actual + 5
		if (to_set < 30):
			to_set = 30
		elif (to_set > 100):
			to_set = 100
		
		self.log('setting vibe motor speed to ' + str(to_set) + ' %')
		
		self.snapshot['vibe_motor'] = to_set
		await self.get_client().set_motors_speed([await self.get_main_motor_speed(), to_set])
		self.window[self.FIELD_VIBRATOR_MOTOR].update_bar(to_set)


	def buttons_changed(self, button_status):
		'''
		Handle a button notification callback
		'''
		self.snapshot['buttons'] = button_status


	def key_state_changed(self, new_value):
		'''
		Handle a change of the key state (eg. user has pressed the central button)
		'''
		self.snapshot['key_state'] = new_value
		
	
	def accelerometer_changed(self, new_value):
		'''
		Handle a change of the accelerometer data
		'''
		self.snapshot['accelerometer'] = new_value
	
	
	def temperature_and_pressure_changed(self, new_value):
		'''
		Handle a change in pressure or temperature data
		'''
		self.snapshot['temperature'] = new_value[0]
		self.snapshot['pressure'] = new_value[1]
		
	
	def rotation_speed_changed(self, new_value):
		'''
		Handle a change in detected motor speed via hall sensors
		'''
		self.snapshot['rotation_speed'] = new_value
		
	
	def depth_changed(self, new_value):
		'''
		Handle a change in detected penetration depth
		'''
		self.snapshot['depth'] = new_value


	async def refresh_status(self):
		'''
		Refresh all static configuration of device, battery level and motors speed.
		Called once on device connection.
		'''
		if self.stopped:
			return
		
		# Read device identifiers
		new_value = await self.get_client().get_manufacturer_name() + ' ' + await self.get_client().get_hardware_revision() + ' (' + await self.get_client().get_mac_address() + ')'
		self.snapshot['device'] = new_value
		self.update(self.FIELD_DEVICE, new_value)
		
		await self.refresh_use_count()
		
		# Check if quick wake-up is enabled
		new_value = await self.get_client().get_wake_up()
		self.snapshot['wake_up'] = new_value
		self.update(self.FIELD_WAKE_UP, 'enabled' if new_value else 'disabled')

		# Check if cruise control is enabled
		new_value = await self.get_client().get_cruise_control()
		self.snapshot['cruise_control'] = new_value
		self.update(self.FIELD_CRUISE_CONTROL, 'enabled' if new_value else 'disabled')

		# Read auto vibrator levels
		new_value = await self.get_client().get_vibration_setting()
		self.snapshot['vibration_setting'] = new_value
		self.update(self.FIELD_VIBRATOR_SETTINGS, ', '.join(str(level) for level in new_value))
		
		await self.refresh_battery_level()
		await self.refresh_motors_speed()
		
		
	async def refresh_battery_level(self):
		'''
		Refresh battery level indication. 
		Called once on device connection and periodically.
		'''
		if self.stopped:
			return
		
		# Read battery status
		level = await self.get_client().get_battery_level()
		logging.info('current battery level is %d', level)
		
		self.window[self.FIELD_BATTERY].update_bar(level)
		self.snapshot['battery'] = level
	

	async def refresh_use_count(self):
		'''
		Refresh use count.
		Called once on device connection.
		'''

		# Read use count
		new_value = await self.get_client().get_use_count()
		self.snapshot['use_count'] = new_value
		self.update(self.FIELD_USE_LOG, str(new_value))
		
	
	async def refresh_motors_speed(self):
		'''
		Refresh motors speed. 
		Called once on device connection and on motors speed change.
		'''
		
		# Read motors speed
		motors_speed = await self.get_client().get_motors_speed()
		self.window[self.FIELD_MAIN_MOTOR].update_bar(motors_speed[0])
		self.window[self.FIELD_VIBRATOR_MOTOR].update_bar(motors_speed[1])
		self.snapshot['main_motor'] = motors_speed[0]
		self.snapshot['vibe_motor'] = motors_speed[1]


	async def sensor_status_updater(self, interval):
		'''
		Status update coroutine. Runs inside asyncio event loop
		'''
		while not self.stopped:
			try:
				if self.get_client() and await self.is_connected():
					self.schedule(self.refresh_sensor_status(), name='refresh_sensor_status', locking=False)
			except Exception as e:
				logging.error('error in refresh_sensor_status task: %s', e)

			if not self.stopped:
				await asyncio.sleep(interval)


	async def refresh_sensor_status(self):
		'''
		Refresh sensor status.
		'''
		if self.stopped:
			return
		
		snapshot = self.snapshot
		
		if 'key_state' in snapshot: 
			self.update(self.FIELD_KEY_STATE, 'authorized' if snapshot['key_state'] else 'not authorized')
		if 'buttons' in snapshot:
			if snapshot['buttons'] == f1client.Buttons.PLUS:
				text = 'PRESSED + BUTTON'
			elif snapshot['buttons'] == f1client.Buttons.MINUS:
				text = 'PRESSED - BUTTON'
			elif snapshot['buttons'] == f1client.Buttons.CENTRAL:
				text = 'PRESSED CENTRAL BUTTON'
			else:
				text = 'no buttons pressed'
			self.update(self.FIELD_BUTTONS, text)
		if 'accelerometer' in snapshot: 
			self.update(self.FIELD_ACCELEROMETER, 'X: ' + str(snapshot['accelerometer'][0]) + ' Y: ' + str(snapshot['accelerometer'][1]) + ' Z: ' + str(snapshot['accelerometer'][2]))
		if 'temperature' in snapshot: 
			self.update(self.FIELD_TEMPERATURE, (str(snapshot['temperature']) + ' C') if snapshot['temperature'] > 0 else '--')
		if 'pressure' in snapshot: 
			self.update(self.FIELD_PRESSURE, (str(snapshot['pressure']) + ' mbar') if snapshot['pressure'] > 0 else '--')
		if 'rotation_speed' in snapshot: 
			self.update(self.FIELD_ROTATION_SPEED, str(snapshot['rotation_speed']) + ' rpm')
		if 'depth' in snapshot: 
			self.update(self.FIELD_DEPTH, str(snapshot['depth']) + ' / 8')
		if 'device' in snapshot: 
			self.update(self.FIELD_DEVICE, snapshot['device'])
		if 'wake_up' in snapshot: 
			self.update(self.FIELD_WAKE_UP, 'enabled' if snapshot['wake_up'] else 'disabled')
		if 'cruise_control' in snapshot: 
			self.update(self.FIELD_CRUISE_CONTROL, 'enabled' if snapshot['cruise_control'] else 'disabled')
		if 'vibration_setting' in snapshot: 
			self.update(self.FIELD_VIBRATOR_SETTINGS, ', '.join(str(level) for level in snapshot['vibration_setting']))
		if 'battery' in snapshot: 
			self.window[self.FIELD_BATTERY].update_bar(snapshot['battery'])
		if 'use_count' in snapshot: 
			self.update(self.FIELD_USE_LOG, str(snapshot['use_count']))
		if 'main_motor' in snapshot: 
			self.update(self.FIELD_MAIN_MOTOR, snapshot['main_motor'])
		if 'vibe_motor' in snapshot: 
			self.update(self.FIELD_VIBRATOR_MOTOR, snapshot['vibe_motor'])
		

	def schedule(self, task, name=None, locking=True):
		'''
		Schedule a task for execution in asyncio event loop.
		Locks the button until the task has completed, then enables buttons depending on application state.
		'''
		async def runner(task):
			logging.debug('runner task %s started', (name or '--'))
			try:
				if locking and not self.stopped: 
					self.lock()
				await task
			except Exception as e:
				logging.exception('error in task %s: %s', (name or '--'), e)
				self.log('error in task: ' + str(e))
			finally:
				logging.debug('runner task %s finished', (name or '--'))
				if locking and not self.stopped: 
					await self.unlock()

		self.loop.create_task(runner(task))


	async def updater(self, interval):
		'''
		Main event loop. Runs inside asyncio event loop
		'''
		
		while not self.stopped:
			try:
				self.window.refresh()
				event, values = self.window.read(timeout=1)
				
				if event is None or event != '__TIMEOUT__':
					logging.debug('EVENT %s', event)
					if event is None or event == self.EVENT_EXIT:
						try:
							if self.get_client() and await self.is_connected():
								await self.disconnect()
						except Exception as e2:
							logging.exception('error closing connection: %s', e2)
						self.loop.create_task(self.close())
						break
					else:
						self.handle_event(event)
					
			except CancelledError as e:
				logging.debug('updater task cancelled')
			
			except Exception as e:
				logging.exception('unexpected error in updater task: %s', e)
			
			if not self.stopped:
				await asyncio.sleep(interval)
		
		logging.info('main GUI update stopped')

	
	def handle_event(self, event):
		if self.locked:
			raise ValueError('could not handle event because application is busy')

		if event == self.EVENT_DISCOVER:
			self.schedule(self.discover(), name='discover')
		elif event == self.EVENT_CONNECT:
			self.schedule(self.connect(), name='connect')
		elif event == self.EVENT_DISCONNECT:
			self.schedule(self.disconnect(), name='disconnect')
		elif event == self.EVENT_RESET_USE_COUNT:
			self.schedule(self.reset_use_count(), name='reset_use_count')
		elif event == self.EVENT_MAIN_MOTOR_MINUS:
			self.schedule(self.decrement_main_motor(), name='decrement_main_motor')
		elif event == self.EVENT_MAIN_MOTOR_PLUS:
			self.schedule(self.increment_main_motor(), name='increment_main_motor')
		elif event == self.EVENT_MAIN_MOTOR_OFF:
			self.schedule(self.shutdown_main_motor(), name='shutdown_main_motor')
		elif event == self.EVENT_VIB_MOTOR_MINUS:
			self.schedule(self.decrement_vibe_motor(), name='decrement_vibe_motor')
		elif event == self.EVENT_VIB_MOTOR_PLUS:
			self.schedule(self.increment_vibe_motor(), name='increment_vibe_motor')
		elif event == self.EVENT_VIB_MOTOR_OFF:
			self.schedule(self.shutdown_vibe_motor(), name='shutdown_vibe_motor')
		else:
			logging.warn('unknown event: %s', event)


	async def battery_level_updater(self, interval):
		'''
		Battery level updater coroutine. Runs inside asyncio event loop
		'''
		try:
			while not self.stopped:
				try:
					if self.get_client() and await self.is_connected():
						self.schedule(self.refresh_battery_level(), name='refresh_battery_level', locking=False)
				except Exception as e:
					logging.error('error in battery_level_updater task: %s', e)
	
				if not self.stopped:
					await asyncio.sleep(interval)

		except CancelledError as e:
			logging.debug('battery_level_updater task cancelled')
		
		except Exception as e:
			logging.exception('unexpected error in battery_level_updater task: %s', e)
		
		logging.info('battery_level_updater stopped')


	async def close(self):
		'''
		Cancel all registered tasks and close window.
		'''
		logging.debug('stopping main GUI instance')
		self.stopped = True
		
		logging.debug('cancelling tasks')
		for task in self.tasks:
			logging.debug('cancelling task %s', task)
			task.cancel()

		logging.debug('waiting for tasks')
		for task in self.tasks:
			while not task.done():
				logging.debug('waiting for task %s', task)
				await asyncio.sleep(1)
		
		logging.debug('stopping main loop')
		await asyncio.sleep(1)
		self.loop.stop()

		logging.debug('closing window')
		self.window.close()
		

if __name__ == '__main__':
	# Configure logging to a basic level
	logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)
	
	# Configure logging for the library
	logging.getLogger(f1client.Constants.LOGGER_NAME).setLevel(logging.DEBUG)
	logging.getLogger(f1client.Constants.LOGGER_IO_NAME).setLevel(logging.INFO)
	logging.getLogger(f1client.Constants.LOGGER_CALLBACK_NAME).setLevel(logging.INFO)
	
	# Configure logging for the backend BLE adapter (bleak)
	logging.getLogger('bleak').setLevel(logging.INFO)

	# Run the sample in asyncio event loop
	loop = asyncio.get_event_loop()
	app = GUISample(loop)
	loop.run_forever()
	loop.close()
