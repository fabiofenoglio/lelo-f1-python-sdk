import asyncio
import logging
import multiprocessing
from datetime import datetime
from matplotlib import pyplot
from matplotlib.animation import FuncAnimation

import lelof1py as f1client

from sample_gui import *


class GraphContext:
	graph_x_count = 0
	graph_x = []
	graph_y = []
	
	figure = None
	line = None
	animation = None
	snapshot = None
	
	limit = 400
	interval = 100
	
	def __init__(self, queue):
		self.snapshot = dict()
		self.queue = queue


	def graph_runner(self):
		logging.info('creating graph')
	
		try:
			self.figure = pyplot.figure()
			self.line, = pyplot.plot_date(self.graph_x, self.graph_y, '-')
			
			self.animation = FuncAnimation(self.figure, self.update_graph, interval=self.interval)
			
			pyplot.show()
	
		except Exception as e:
			logging.exception('error creating graph: %s', e)
			raise e
	
	
	def update_graph(self, frame):
		try:
			if not self.queue:
				return
			
			if not self.queue.empty():
				read = self.queue.get_nowait()
				if read:
					logging.debug('got data from queue, setting %s = %s', read[0], read[1])
					self.snapshot[read[0]] = read[1]
				
			logging.debug('updating graph')

			if 'pressure' in self.snapshot:
				self.graph_x.append(datetime.now())
				self.graph_y.append(self.snapshot['pressure'])
				self.graph_x_count = self.graph_x_count + 1
				
				if self.graph_x_count > self.limit:
					self.graph_x = self.graph_x[-self.limit:]
					self.graph_y = self.graph_y[-self.limit:]
					self.graph_x_count = self.limit
				
				self.line.set_data(self.graph_x, self.graph_y)
				self.figure.gca().relim()
				self.figure.gca().autoscale_view()
			
			logging.debug('updated graph')
			return self.line,
	
		except Exception as e:
			logging.exception('error updating graph: %s', e)
			raise e


# Initialize context with service
class GUISampleGraph(GUISample):
	'''
	Complete sample of device discovery, connection and control with simple GUI 
	'''
	
	def __init__(self, queue, loop, refresh_interval=1/100):
		'''
		Initializes the window and prepares the layout
		'''
		self.queue = queue
		super(GUISampleGraph, self).__init__(loop, refresh_interval)


	async def post_construct(self):
		'''
		Method to be overrided
		'''
		self.tasks.append(self.loop.create_task(self.sensor_status_updater(1)))
		
		
	def temperature_and_pressure_changed(self, new_value):
		'''
		Handle a change in pressure or temperature data
		'''
		super(GUISampleGraph, self).temperature_and_pressure_changed(new_value)
		self.queue.put(['pressure', new_value[1]])


if __name__ == '__main__':
	# Configure logging to a basic level
	logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)
	
	# Configure logging for the library
	logging.getLogger(f1client.Constants.LOGGER_NAME).setLevel(logging.DEBUG)
	logging.getLogger(f1client.Constants.LOGGER_IO_NAME).setLevel(logging.INFO)
	logging.getLogger(f1client.Constants.LOGGER_CALLBACK_NAME).setLevel(logging.INFO)
	
	logging.getLogger('matplotlib').setLevel(logging.INFO)
	
	# Configure logging for the backend BLE adapter (bleak)
	logging.getLogger('bleak').setLevel(logging.INFO)


	# use the multiprocessing module to perform the plotting activity in another process (i.e., on another core):
	queue = multiprocessing.Queue(1000)
	gc = GraphContext(queue)
	job_for_another_core = multiprocessing.Process(target=gc.graph_runner)
	

	# Run the sample in asyncio event loop
	loop = asyncio.get_event_loop()
	app = GUISampleGraph(queue, loop)
	
	job_for_another_core.start()
	
	loop.run_forever()
	loop.close()
