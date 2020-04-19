import asyncio
import logging

import lelof1py as f1client


async def run():
	'''
	Sample for direct usage without a GUI.

	First, an attempt to find the device is run via discover() method;
	then, if a device is found, a connection will be automatically attempted.
	
	In case of successfull connection, information on device and sensors are retrieved.
	Notification on-push from BLE layer is demonstrated via the notify_buttons method.
	'''
	
	# instantiate async client
	client = f1client.AsyncClient()
	
	# discovery (for 60 seconds). Only F1s devices will be returned
	logging.info('running discovery to find your F1s ...')
	devices = await client.discover(timeout=60)

	if not len(devices):
		logging.info('No devices found!')
		return
	
	logging.info('Device found! Trying to connect ...')
	await client.connect(devices[0].address, timeout=30)

	logging.info('Device connected!')
	
	def cb_handler(button_status):
		if button_status == f1client.Buttons.PLUS:
			text = 'PRESSED + BUTTON'
		elif button_status == f1client.Buttons.MINUS:
			text = 'PRESSED - BUTTON'
		elif button_status == f1client.Buttons.CENTRAL:
			text = 'PRESSED CENTRAL BUTTON'
		else:
			text = 'no buttons pressed'
	
		logging.info('BUTTON STATE: %s', text)

	try:
		while not await client.get_key_state():
			logging.info('Not authorized. Please, PRESS THE CENTRAL BUTTON')
			await asyncio.sleep(2)
		
		logging.debug('now stopping motors for initialization')
		await client.stop_motors()
		
		# Read device info
		logging.info('get_manufacturer_name: %s', await client.get_manufacturer_name())
		logging.info('get_model_number: %s', await client.get_model_number())
		logging.info('get_hardware_revision: %s', await client.get_hardware_revision())
		logging.info('get_firmware_revision: %s', await client.get_firmware_revision())
		logging.info('get_software_revision: %s', await client.get_software_revision())
		logging.info('get_mac_address: %s', await client.get_mac_address())
		logging.info('get_serial_number: %s', await client.get_serial_number())
		logging.info('get_chip_id: %s', await client.get_chip_id())
		logging.info('get_device_name: %s', await client.get_device_name())
		logging.info('get_system_id: %s', await client.get_system_id())
		logging.info('get_pnp_id: %s', await client.get_pnp_id())
		logging.info('get_ieee_11073_20601: %s', await client.get_ieee_11073_20601())
		
		# Read sensors data
		logging.info('get_battery_level: %s', await client.get_battery_level())
		logging.info('get_temperature: %s', await client.get_temperature())
		logging.info('get_pressure: %s', await client.get_pressure())
		logging.info('get_accelerometer: %s', await client.get_accelerometer())
		logging.info('get_depth: %s', await client.get_depth())
		logging.info('get_rotation_speed: %s', await client.get_rotation_speed())
		logging.info('get_use_count: %s', await client.get_use_count())

		# Register for notification on buttons press
		await client.notify_buttons(cb_handler)

		logging.info('setting motors speed to 0/40')
		await client.set_motors_speed([0, 40])

		logging.info('waiting 30 seconds, try pressing the buttons')
		await asyncio.sleep(30)

		logging.info('finished, now disconnecting')

	except Exception as e:
		logging.exception('error in main routine: %s', e)

	finally:
		# shutdown and disconnect the client if it is connected
		if client.is_connected():
			if await client.is_authorized():
				await client.shutdown()
			await client.disconnect()


if __name__ == '__main__':
	# Configure logging format
	logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)
	
	# Configure logging for the library
	logging.getLogger(f1client.Constants.LOGGER_NAME).setLevel(logging.DEBUG)
	logging.getLogger(f1client.Constants.LOGGER_CALLBACK_NAME).setLevel(logging.INFO)
	logging.getLogger(f1client.Constants.LOGGER_IO_NAME).setLevel(logging.DEBUG)
	
	# Configure logging for the backend BLE adapter (bleak)
	logging.getLogger('bleak').setLevel(logging.DEBUG)

	# Run the routine inside the main event loop
	loop = asyncio.get_event_loop()
	loop.run_until_complete(run())