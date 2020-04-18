import asyncio
import time
import logging
import socket
import json
import re

from .definitions import *
from .async_client import *
from asyncio.futures import CancelledError


class SocketConnection:
	'''
	Holds information for connected clients.
	'''

	id = None
	name = None
	authorized = False
	locking = False

	def __init__(self, id):
		self.id = id
		
	def is_authorized(self):
		return self.authorized
	
	def authorize(self):
		self.authorized = True


class SocketServer():
	'''
	Asynchronous LELO F1 SDK SOCKET server.
	Configurable with standard logging.
	'''
	logger = logging.getLogger(Constants.LOGGER_SOCKET_SERVER_NAME)
	logger_io = logging.getLogger(Constants.LOGGER_IO_NAME)
	
	SOCKET_ENCODING = 'utf8'

	def __init__(self, client_provider, ip_address, port):
		'''
		Instantiate the socket server.
		Takes a client or a client provider as only parameter.
		'''
		self.logger.debug('instantiating LELO F1 SDK SOCKET server')
		self.stopped = False
		self.stop_requested = False
		
		if isinstance(client_provider, AsyncClient):
			self.client_provider = None
			self.client = client_provider
		else:
			self.client_provider = client_provider
			self.client = None
		
		self.ip_address = ip_address
		self.port = port
		self.clients = {}
		self.blocked_clients = []
		
		self.authorization_handler = None
		self.command_handler = None

		self.callbacks = dict()


	def set_authorization_handler(self, handler):
		'''
		Set the async handler to be used to authorize client connections.
		'''
		self.authorization_handler = handler


	def set_command_handler(self, handler):
		'''
		Set the async handler to be used to execute commands.
		'''
		self.command_handler = handler

	
	def on_after_command(self, callback):
		'''
		Register a function to be called after every succesfull command 
		'''
		self._register_callback('AFTER_COMMAND', callback)

	
	def on_client_connected(self, callback):
		'''
		Register a function to be called when a client disconnects
		'''
		self._register_callback('CLIENT_CONNECT', callback)

	
	def on_client_disconnect(self, callback):
		'''
		Register a function to be called when a client disconnects
		'''
		self._register_callback('CLIENT_DISCONNECT', callback)


	async def _dispatch_callback(self, key, *args):
		'''
		Internal use only.
		'''
		if not key in self.callbacks:
			return
		for cb in self.callbacks[key]:
			try:
				await cb(*args)
			except Exception as e:
				self.logger.exception('error in user callback: %s', e)


	def _register_callback(self, key, cb):
		'''
		Internal use only.
		'''
		if not key in self.callbacks:
			self.callbacks[key] = []
		self.callbacks[key].append(cb)
		

	def get_active_clients(self):
		'''
		Returns a list of SocketConnection objects representing the active clients.
		'''
		return self.clients.values()


	def get_client(self):
		'''
		Get the device client from the fixed one passed at construction or from the provider.
		'''
		if self.client_provider:
			return self.client_provider()
		elif self.client:
			return self.client
		else:
			return None


	def stop(self):
		self.logger.debug('scheduling socket server stop request')
		if not self.stop_requested:
			self.stop_requested = True
			self.stopped = True


	async def run_server(self, loop):
		'''
		Socket server coroutine.
		Runs inside asyncio event loop passed as parameter.
		'''
		try:
			self.logger.info('running socket server')
			self.loop = loop
		
			self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.logger.info('opening socket on %s:%d', self.ip_address, self.port)
			
			self.socket.bind((self.ip_address, self.port))
			self.socket.listen(1) 
			self.socket.setblocking(False)
			
			self.logger.info('socket server waiting for connection')
			while not self.stopped:
				try:
					client, _ = await asyncio.wait_for(
		                self._accept_connection(),
		                timeout=3,
		                loop=self.loop,
		            )
				except asyncio.futures.TimeoutError:
					if self.stopped:
						break
					continue

				except CancelledError as sock_accept_exception:
					self.logger.warning('socket accept operation cancelled: %s', sock_accept_exception)
					break
				except Exception as sock_accept_exception:
					self.logger.exception('socket GENERIC EXCEPTION: %s', sock_accept_exception)
					break
				
				self.logger.info('socket server received a connection from ' + str(client.getpeername()))
				self.loop.create_task(self.handle_client(client))

		except Exception as ext:
			self.logger.exception('error running socket server: %s', ext)

		if False and self.socket:
			self.logger.debug('closing socket following close request')
			self.socket.close()
			self.logger.debug('closed socket following close request')

		self.logger.info('socket server stopped')


	async def _accept_connection(self):
		return await self.loop.sock_accept(self.socket)


	async def _receive_connection(self, client, limit):
		return await self.loop.sock_recv(client, limit)


	async def handle_client(self, client):
		'''
		Handles commands from a client.
		Automatically translates data from/to JSON <-> dictionary.
		'''
		client_info = self.get_or_create_client_info(client)
		self.logger.info( (client_info.name or client_info.id) + ' CONNECTED')
		
		await self._dispatch_callback('CLIENT_CONNECT', client_info)
		
		try:
			self.logger.info('socket server serving client %s', client.getpeername())
			
			request = None
			
			while not self.stopped:
				try:
					request_raw = await asyncio.wait_for(
		                self._receive_connection(client, 1023),
		                timeout=3,
		                loop=self.loop,
		            )
				except asyncio.futures.TimeoutError:
					if self.stopped:
						break
					continue

				if request_raw is None or len(request_raw) == 0:
					self.logger.info('received empty packet, disconnecting')
					break
				request = request_raw.decode(self.SOCKET_ENCODING)
				try:
					payload = json.loads(request)
					
					self.logger_io.debug('RECEIVED %s', request)
					
					response = json.dumps(await self.handle_command(client_info, payload))
					
				except Exception as e:
					self.logger.exception('error handling client command: %s', e)
					response = json.dumps(self.response_error(e))

				self.logger_io.debug('SEND %s', response)
				
				await self.loop.sock_sendall(client, (response + '\n').encode(self.SOCKET_ENCODING))
				
				if not client_info.id in self.clients:
					self.logger.info('command requested disconnection')
					break

			self.logger.info('socket server closing connection')
			client.close()
			
		except CancelledError as sock_accept_exception:
			self.logger.warning('socket read operation cancelled: %s', sock_accept_exception)
		except Exception as ext:
			self.logger.exception('error handling client: %s', ext)
		finally:
			if client_info.id in self.clients:
				del self.clients[client_info.id]
			self.logger.info( (client_info.name or client_info.id) + ' DISCONNECTED')
		
		await self._dispatch_callback('CLIENT_DISCONNECT', client_info)


	def get_or_create_client_info(self, client):
		client_id = client.getpeername()[0] + ':' + str(client.getpeername()[1])
		if client_id in self.clients:
			self.logger.debug('client %s is known already', client_id)
			return self.clients[client_id]
		else:
			self.logger.debug('client %s is a new client, registering', client_id)
			client_info = SocketConnection(client_id)
			self.clients[client_id] = client_info
			return client_info


	async def handle_command(self, client_info, payload):
		'''
		Handle a single command received from socket.
		client_id is the client identifier in 'IP:PORT' format.
		payload is a dictionary obtained from json deserialization.
		'''
		try:
			if not payload or not 'command' in payload:
				raise ValueError('Malformed command: ' + str(payload))

			command = payload['command'].lower() if 'command' in payload else None
			arguments = payload['arguments'] if 'arguments' in payload else []

			self.logger.info('received command: ' + (command) + (' from ' + client_info.name if client_info.name else ''))
			
			data = await self.execute_command(client_info, command, arguments)
			
			await self._dispatch_callback('AFTER_COMMAND', client_info, command, arguments, data)

			return self.response_ok(data)

		except Exception as e:
			self.logger.exception('error handling command: %s', e)
			return self.response_error(e)


	async def execute_command(self, client_info, command, arguments):
		'''
		Executes the command on local first and on device if not a local command.
		'''
		command = re.sub(r'[^a-z0-9_]', '', command.lower())

		self.logger.debug('attempting to run command %s as a managed command', command)
		handled, data = await self.execute_command_managed(client_info, command, arguments)
		
		if not handled and self.command_handler:
			self.logger.debug('attempting to run command %s from registered command handler', command)
			handled, data = await self.command_handler(client_info, command, arguments)
		
		if not handled:
			self.logger.debug('attempting to run command %s as a device command', command)
			data = await self.execute_command_device(client_info, command, arguments)
		
		return data


	async def execute_command_managed(self, client_info, command, arguments):
		'''
		Executes a managed command.
		'''
		if hasattr(self, 'command_' + command):
			return (True, await getattr(self, 'command_' + command)(client_info, arguments))
		else:
			self.logger.debug('command %s is not a managed command', command)
			return (False, None)


	async def execute_command_device(self, client_info, command, arguments):
		'''
		Executes a command directly on the device backend.
		'''
		self.assert_authorized(client_info)
		
		if command.startswith('_'):
			raise ValueError('Forbidden command ' + command)

		if command.startswith('notif'):
			raise ValueError('Forbidden notification command ' + command)
		
		handler = getattr(self.get_client(), command)
		if not handler:
			raise ValueError('Unknown command ' + command)

		data = await handler(*arguments)
		return data
	
	
	def assert_authorized(self, client_info):
		'''
		Shortcut method to check that the client has been authorized.
		'''
		if not client_info or not client_info.is_authorized():
			raise ValueError('client is not authorized')


	def response_ok(self, data=None):
		out = dict()
		out['status'] = 'OK'
		if data is not None:
			out['data'] = data
		return out


	def response_error(self, e):
		out = dict()
		out['status'] = 'ERROR'
		out['message'] = str(e)
		return out


	async def command_ping(self, client_info, arguments):
		'''
		Checks that the connection works.
		'''
		return 'pong'


	async def command_name(self, client_info, arguments):
		'''
		Associates a name to the client.
		'''
		client_info.name = str(arguments[0])


	async def command_quit(self, client_info, arguments):
		'''
		Closes the connection.
		'''
		del self.clients[client_info.id]


	async def command_authorized(self, client_info, arguments):
		'''
		Checks wether client has been authorized.
		'''
		if client_info.id in self.blocked_clients:
			return 'BLOCKED'
		else:
			return client_info.authorized


	async def command_connected(self, client_info, arguments):
		'''
		Checks wether client device is connected.
		'''
		return self.get_client().is_connected()
	
	
	async def command_authorize(self, client_info, arguments):
		'''
		Requests user authorization if needed
		'''
		if client_info.authorized:
			return True
		
		if client_info.id in self.blocked_clients:
			return False
		
		if not self.authorization_handler:
			raise ValueError('No authorization handler registered')

		result = await self.authorization_handler(client_info, arguments)
		
		identifier = client_info.name or client_info.id
		
		if result:
			self.logger.info('granted control to ' + identifier)
			client_info.authorized = True
		else:
			self.logger.warn('blocked control from ' + identifier)
			self.blocked_clients.append(client_info.id)
