# -*- coding: utf-8 -*-
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from airflow.hooks.base_hook import BaseHook
from airflow.exceptions import AirflowException
import grpc
from google import auth as google_auth
from google.auth import jwt as google_auth_jwt
from google.auth.transport import grpc as google_auth_transport_grpc

class GrpcHook(BaseHook):
	"""
	General interaction with GRPC servers.
	"""

	def __init__(self, grpc_conn_id, interceptors=[], custom_connection_func=None):
		self.grpc_conn_id = grpc_conn_id
		self.conn = self.get_connection(self.grpc_conn_id)
		self.extras = conn.extra_dejson
		self.interceptors = interceptors
		self.custom_connection_func = custom_connection_func

	def get_conn(self):
		if "://" in self.conn.host:
            base_url = self.conn.host
        else:
            # schema defaults to HTTP
            schema = self.conn.schema if self.conn.schema else "http"
            base_url = schema + "://" + self.conn.host

		if self.conn.port:
            base_url = base_url + ":" + str(self.conn.port) + "/"

        auth_type = self._get_field("auth_type")

		if auth_type == "NO_AUTH":
			channel = grpc.insecure_channel(base_url)
		elif auth_type == "SSL" or auth_type == "TLS":
			credential_file_name = self._get_field("credential_pem_file")
			creds = grpc.ssl_channel_credentials(open(credential_file_name).read())
			channel = grpc.secure_channel(base_url, creds)
		elif auth_type == "JWT_GOOGLE":
			credentials, _ = google_auth.default()
			jwt_creds = google_auth_jwt.OnDemandCredentials.from_signing_credentials(
			    credentials)
			channel = google_auth_transport_grpc.secure_authorized_channel(
			    jwt_creds, None, base_url)
		elif auth_type == "OATH_GOOGLE":
			scopes = self._get_field("scopes").split(",")
			credentials, _ = google_auth.default(scopes=scopes)
			request = google_auth_transport_requests.Request()
			channel = google_auth_transport_grpc.secure_authorized_channel(
			    credentials, request, base_url)
		elif auth_type == "CUSTOM":
			if not self.custom_connection_func:
				raise AttributeError("Customized connection function not set, not able to establish a channel")
			channel = self.custom_connection_func(self.conn)

		if self.interceptors:
			for interceptor in self.interceptors:
				channel = grpc.intercept_channel(channel,
                                                 interceptor)

		return channel

	def run(self, stub_class, call_func, streaming=False, data={}):
		 with self.get_conn() as channel:
		 	stub = stub_class(channel)
			try:
			 	response = stub.call_func(**data)
			 	if not streaming:
			 		return response

			 	for single_response in response:
			 		yield single_response
			except grpc.FutureTimeoutError:
				self.log.exception(
					"Timeout when calling the grpc service: %s, method: %s" % (stub_class.__name__, call_func.__name__))

	def _get_field(self, feild_name, default=None):
        """
        Fetches a field from extras, and returns it. This is some Airflow
        magic. The grpc hook type adds custom UI elements
        to the hook page, which allow admins to specify scopes, credential pem files, etc.
        They get formatted as shown below.
        """
        full_field_name = 'extra__grpc__{}'.format(f)
        if full_field_name in self.extras:
            return self.extras[full_field_name]
        else:
            return default
