# LELO F1 SDK Python client

Python package to provide a BLE client to LELO's F1 SDK.

  - Supports python 3.4+
  - Supports standard python logging library

# Features

Supports the features listed on the official [BLE documentation page](https://github.com/LELO-Devs/F1s-SDK/blob/master/BLE-Specs.md) for the device.


### Dependencies

Requires:

* asyncio - async coroutines management
* bleak - cross-platform BLE client


### Installation

This package requires python 3.4.

You can install from pip:
```sh
$ pip install lelof1py
```

**Warning**: currently, on python 3.8 there could be some problems with installing the dependency `pythonnet` via `pip`.
If you have problems running `pip install lelof1py` you can:
* try using a python version lower than 3.8, ideally 3.6
* use a virtual environment with a lower python version (ideally 3.6)
* open an issue

### Demo

Two examples are included in this repository: `sample_cli.py` and `sample_gui.py`.
In order to run the examples:

* ensure lelof1py is installed by running ```pip install lelof1py```
* ensure PySimpleGUI is installed by running ```pip install pysimplegui```
* run either ```python sample_cli.py``` or ```python sample_gui.py```

CLI sample
![CLI sample](https://raw.githubusercontent.com/fabiofenoglio/lelo-f1-python-sdk/master/docs/screenshots/cli0.jpg)

GUI sample
![GUI sample](https://raw.githubusercontent.com/fabiofenoglio/lelo-f1-python-sdk/master/docs/screenshots/cli0.jpg)


### Usage

See the included samples for both inline and GUI usage.

```python
import asyncio
import logging
import lelof1py as f1client

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logging.getLogger(f1client.Constants.LOGGER_NAME).setLevel(logging.INFO)
logging.getLogger(f1client.Constants.LOGGER_IO_NAME).setLevel(logging.WARN)
logging.getLogger('bleak').setLevel(logging.INFO)

async def run():
	client = f1client.AsyncClient() # instantiate async client

	logging.info('running discovery to find your F1s ...') 
	devices = await client.discover(timeout=60)

	if not len(devices):
		logging.info('No devices found!')
		return
	
	logging.info('Device found! Trying to connect ...')
	await client.connect(devices[0].address, timeout=30)

	logging.info('Device connected!')

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
	
	# Read sensors data
	logging.info('get_battery_level: %s', await client.get_battery_level())
	logging.info('get_temperature: %s', await client.get_temperature())
	logging.info('get_pressure: %s', await client.get_pressure())
	logging.info('get_accelerometer: %s', await client.get_accelerometer())
	logging.info('get_depth: %s', await client.get_depth())
	logging.info('get_rotation_speed: %s', await client.get_rotation_speed())
	logging.info('get_use_count: %s', await client.get_use_count())
	
	logging.info('shutting down device')
	await client.shutdown()


# Run the routine inside the main event loop
loop = asyncio.get_event_loop()
loop.run_until_complete(run())
```

### Available methods

The following methods are available on client object.
Note that most methods are async and should be awaited.


| Method        | Input         | Output| Async  |
| ------------- |-------------:| -----:| ------:|
|	`connect` | `string` **address**, `int` timeout (seconds, optional) | -- | yes |
|	`disable_cruise_control` |  --      | -- | yes |
|	`disable_wake_up` |  --      | -- | yes |
|	`disconnect` |  --      | -- | yes |
|	`discover` | `int` timeout (seconds, optional), `string` address (optional)     | list of [`BLEDevice`](https://bleak.readthedocs.io/en/latest/api.html#bleak.backends.device.BLEDevice) | yes |
|	`enable_cruise_control` | `boolean` reset (optional)      | -- | yes |
|	`enable_wake_up` |  --      | `boolean` | yes |
|	`get_accelerometer_x` |  --      | `int` | yes |
|	`get_accelerometer_y` |  --      | `int` | yes |
|	`get_accelerometer_z` |  --      | `int` | yes |
|	`get_accelerometer` |  --      | `int` tuple(x, y, z) | yes |
|	`get_battery_level` |  --      | `int` from 0 to 100 | yes |
|	`get_buttons_status` |  --      | `lelof1py.Buttons` | yes |
|	`get_chip_id` |  --      | `string` | yes |
|	`get_cruise_control` |  --      | `boolean` | yes |
|	`get_depth` |  --      | `int` from 0 to 8 | yes |
|	`get_device_name` |  --      | `string` | yes |
|	`get_firmware_revision` |  --      | `string` | yes |
|	`get_hardware_revision` |  --      | `string` | yes |
|	`get_ieee_11073_20601` |  --      | `string` | yes |
|	`get_key_state` |  `boolean` silent (optional)      | `boolean` | yes |
|	`get_mac_address` |  --      | `string` | yes |
|	`get_main_motor_speed` |  --      | `int` from 0 to 100 | yes |
|	`get_manufacturer_name` |  --      | `string` | yes |
|	`get_model_number` |  --      | `string` | yes |
|	`get_motors_speed` |  --      | `int` tuple(main, vibe) from 0 to 100 | yes |
|	`get_pnp_id` |  --      | `string` | yes |
|	`get_pressure` |  --      | -- | `float`, in mbar  |
|	`get_rotation_speed` |  --      | `int` (RPS) | yes |
|	`get_serial_number` |  --      | `string` | yes |
|	`get_software_revision` |  --      | `string` | yes |
|	`get_system_id` |  --      | `string` | yes |
|	`get_temperature_and_pressure` |  --      | `float` tuple(temperature, pressure) | yes |
|	`get_temperature` |  --      | -- | `float`, in C degrees |
|	`get_use_count` |  --      | `int` | yes |
|	`get_vibration_setting` |  --      | `int` tuple(V0, ... V7) from 0 to 100 | yes |
|	`get_vibration_speed` |  --      | `int` from 0 to 100 | yes |
|	`get_wake_up` |  --      | `boolean` | yes |
|	`is_authorized` |  --      | `boolean` | yes |
|	`is_connected` |  --      | `boolean` | no |
|	`notify_accelerometer` | `callback` user_callback      | `handler` | yes |
|	`notify_buttons` | `callback` user_callback     | `handler` | yes |
|	`notify_depth` | `callback` user_callback      | `handler` | yes |
|	`notify_key_state` | `callback` user_callback     | `handler` | yes |
|	`notify_rotation_speed` | `callback` user_callback     | `handler` | yes |
|	`notify_temperature_and_pressure` | `callback` user_callback     | `handler` | yes |
|	`ping` |  --      | -- | yes |
|	`reset_use_count` |  --      | -- | yes |
|	`set_main_motor_speed` |  `int` from 0 to 100       | -- | yes |
|	`set_motors_speed` | `int` tuple(main, vibe) from 0 to 100      | -- | yes |
|	`set_vibration_setting` |  --      | -- | yes |
|	`set_vibration_speed` |  `int` from 0 to 100       | -- | yes |
|	`shutdown` |  --      | -- | yes |
|	`stop_motors` |  --      | -- | yes |
|	`unregister` | `handler` callback_handler     | -- | yes |
|	`verify_accelerometer` |  --      | -- | yes |


### Development

Want to contribute? Great! Please, shoot me an [email](mailto:development@fabiofenoglio.it)
