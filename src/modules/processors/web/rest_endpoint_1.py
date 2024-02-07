"""
**Note:**   This module can not be dynamically started. You have to restart (and automatically load) the complete app.
**Note:**   When you want to use the module inside docker,
            you have to specify the ports used in the configuration file also inside `docker-compose.yml`
            (e.g. `ports: - "8123:8123"`)
            When running in a container make the host address is `host: 0.0.0.0` in the configuration file.
            You can access the endpoints subsequently via `http://127.0.0.1:8123` or your machine ip.
**Note:**   In the case for an unauthorized access, the response contains only a content body
            (response.content and not response.json()).

When the module is added to the configuration,
the data changes are saved in the following way in the response:

```json
[{
  "measurement": "measurement",
  "tags": {"level": "INFO", "module": "excel_output_module"},
  "time": "2020-11-27 09:58:23.017578",
  "fields": {"level": "INFO", "module": "excel_output_module"}
}]
```

The REST endpoint module returns responses in json format when receiving a request.

Possible status codes:

- 200: Success
- 404: Bad request
- 405: Method not allowed
- 500: Internal server error

#### Example Response for PUT, POST, and DELETE requests

```json
{
   "error": false,
   "message": "Success",
   "data": "Optional information."
}
```

#### Example Response for GET requests

```json
[{
  "measurement": "measurement",
  "tags": {"level": "INFO", "module": "excel_output_module"},
  "time": "2020-11-27 09:58:23.017578",
  "fields": {"level": "INFO", "module": "excel_output_module"}
}]
```

If we receive a field with `event: delete` and an `id` field is given, the object is removed.
If `id` field is given and the object already exists, the object is updated.
Otherwise, the object is added.

If we receive a DELETE HTTP request, a field or tag (`event: delete`) is added.
If it is an POST or PUT request, the received data is forwarded without further adjustments.
"""
from dataclasses import dataclass, field
from threading import Thread
from typing import Optional, Any, Tuple, Union
import os
import collections
import logging
import json

# Internal imports.
import config
import data_layer
from modules.processors.base.base import AbstractProcessorModule, models


class ServerThread(Thread):
    """
    This is a thread class, which implements a shutdown method for stopping the server.

    :param app: The flask app.
    :param host: The host address.
    :param port: The port.
    :param name: The name of the thread.
    """

    def __init__(self, app, host: str, port, name: str):
        Thread.__init__(self, name="REST_Server_Processor_Module_{0}".format(name), daemon=True)
        self.srv = werkzeug.serving.make_server(host=host, port=port, app=app, threaded=True)
        self.ctx = app.app_context()
        # self.ctx.push()  # This causes the exception: 'popped wrong app context' if not initially started.

    def run(self):
        """
        Starts the server (is called by the Thread class).
        """
        self.srv.serve_forever()

    def shutdown(self):
        """
        Stops the server.
        """
        self.srv.shutdown()


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module acts as a REST endpoint enabling GET, POST, PUT, and DELETE requests."
    """A short description."""
    author: str = "Colin Reiff"
    """The author name."""
    email: str = "colin.reiff@collectu.de"
    """The email address of the author."""
    deprecated: bool = False
    """Is this module deprecated."""
    third_party_requirements: list[str] = ["Werkzeug==2.0.2", "Flask-HTTPAuth==4.5.0", "Flask==2.0.2",
                                           "Flask-Cors==3.0.10"]
    """Define your requirements here."""
    field_requirements: list[str] = []
    """Data validation requirements for the fields dict."""
    tag_requirements: list[str] = []
    """Data validation requirements for the tags dict."""

    @dataclass
    class Configuration(models.ProcessorModule):
        """
        The configuration model of the module.
        """
        measurement: str = field(
            metadata=dict(description="The measurement name.",
                          required=True),
            default=None)
        path: str = field(
            metadata=dict(description="The path to the endpoint (e.g. `/path`) including `/`.",
                          required=False),
            default="/path")
        host: str = field(
            metadata=dict(description="The host address of the server.",
                          required=False),
            default="0.0.0.0")
        port: int = field(
            metadata=dict(description="The port of the server.",
                          required=False),
            default=8125)
        anonymous: bool = field(
            metadata=dict(description="Is authentication required.",
                          required=False),
            default=True)
        username: str = field(
            metadata=dict(description="The username for the basic authentication.",
                          required=False),
            default='admin')
        password: str = field(
            metadata=dict(description="The password for the basic authentication.",
                          required=False),
            default='admin')
        enable_update_or_delete: bool = field(
            metadata=dict(description="If enabled, it is checked if an `id` field exists. "
                                      "If yes, the existing object is updated and in the case that a field "
                                      "`event: delete` is given, the existing object is deleted.",
                          required=False),
            default=True)
        buffer_size: int = field(
            metadata=dict(description="The number of returned elements.",
                          required=False),
            default=100)
        accept_all: bool = field(
            metadata=dict(description="If the json is a dict, we directly parse it into the fields. Otherwise, "
                                      "we only except the keys `fields` and `tags`.",
                          required=False),
            default=True)

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)
        self.server = None
        """The werkzeug server."""
        self.circular_buffer = collections.deque(maxlen=self.configuration.buffer_size)
        """List containing the data elements (number of elements = buffer_size)."""

    @classmethod
    def import_third_party_requirements(cls) -> bool:
        """
        Check if all third party requirements are successfully imported.
        Raises an ImportError if the import was not successful.

        :returns: True if the import was successful.
        """
        try:
            # Import third party packages here and mark them as global.
            global flask
            import flask
            global flask_httpauth
            import flask_httpauth
            global werkzeug
            import werkzeug
            global CORS
            from flask_cors import CORS
            return True
        except Exception:
            raise ImportError("Could not import required packages. Please install '{0}'."
                              .format(' '.join(map(str, cls.third_party_requirements))))

    def start(self) -> bool:
        """
        Method for starting the module. Is called by the main thread.

        :returns: True if successfully connected, otherwise false.
        """
        try:
            # Instantiate the Flask app.
            app = flask.Flask(self.configuration.id)
            app.debug = False

            # Allow CORS for all domains on all routes.
            CORS(app)

            # Set the 'werkzeug' logger to only error messages and completely disable the app logger.
            log = logging.getLogger('werkzeug')
            log.setLevel(logging.ERROR)
            # This should suppress "Serving Flask app ..."
            os.environ['WERKZEUG_RUN_MAIN'] = 'true'

            auth = flask_httpauth.HTTPBasicAuth()
            if not self.configuration.anonymous:
                users = {self.configuration.username: werkzeug.security.generate_password_hash(
                    self.configuration.password)}

            @auth.verify_password
            def verify_password(username: str, password: str) -> Optional[str]:
                """
                Verify the password. If no authentication is required, we return an empty username.

                :param username: The username.
                :param password: The password.

                :returns: The username if authenticated, an empty string if no authentication is necessary
                or otherwise None.
                """
                if not self.configuration.anonymous:
                    if username in users and werkzeug.security.check_password_hash(users.get(username), password):
                        return username
                    else:
                        self.logger.error("The given credentials (username: '{0}' and password: '{1}') were wrong."
                                          .format(username, password))
                        return None
                else:
                    return ""

            @app.route('/<var>', methods=['GET', 'POST', 'PUT', 'DELETE'])
            @auth.login_required
            def endpoint(var) -> Optional[Tuple[Any, int]]:
                """
                Function gets called when request is send to server.

                :param var: The requested endpoint.

                :returns: A json object and a status code.
                """
                if flask.request.method == "GET" and "/" + var == self.configuration.path:
                    return json.dumps(list(self.circular_buffer), default=str), 200
                else:
                    if flask.request.is_json:
                        if "/" + var == self.configuration.path:
                            self._view(body=flask.request.get_json(),
                                       method=flask.request.method)
                            return flask.jsonify(error=False,
                                                 message="Successfully received input data.",
                                                 data=""), 200
                        else:
                            return flask.jsonify(error=True,
                                                 message="Endpoint is not defined.",
                                                 data=str("/" + var)), 404
                    else:
                        return flask.jsonify(error=True,
                                             message="Could not process input data. "
                                                     "Please only send json in the form of key value pairs.",
                                             data=str(flask.request.get_data())), 400

            @app.errorhandler(werkzeug.exceptions.HTTPException)
            def handle_exception(e) -> Tuple[Any, int]:
                """
                Return JSON instead of HTML for HTTP errors.

                :param e: The occurred exception.
                """
                return flask.jsonify(error=True,
                                     message=e.name,
                                     data=e.description), e.code

            self.server = ServerThread(app=app,
                                       host=self.configuration.host,
                                       port=self.configuration.port,
                                       name=self.configuration.id)
            self.server.start()

            self.logger.info("Successfully created server {0}."
                             .format(f"{self.configuration.host}:{self.configuration.port}"))
            return True

        except Exception as e:
            self.logger.critical("Something unexpected went wrong while trying to create server. {0}"
                                 .format(str(e)), exc_info=config.EXC_INFO)
            return False

    def stop(self):
        """
        Method for stopping the output module. Is called by the main thread.
        """
        if hasattr(self.server, 'shutdown'):
            self.server.shutdown()

    def _view(self, body: Union[dict, str], method: str):
        """
        Process the HTTP request.

        :param body: The input_body containing the fields, tags and measurement name to be stored.
        :param method: The HTTP method. Can be POST, PUT, or DELETE.
        """
        try:
            # Convert json formatted string to dict if it isn't already a dict.
            if not isinstance(body, dict):
                body = json.loads(body)

            fields = {}
            tags = {}
            if self.configuration.accept_all and isinstance(body, dict):
                fields = body
            elif isinstance(body, dict):
                for key, value in body.get('fields', {}).items():
                    fields[key] = value
                for key, value in body.get('tags', {}).items():
                    tags[key] = value
            else:
                raise Exception("The received body is not a valid json dictionary: {0}".format(str(body)))

            # If it is a DELETE method, we add an event field.
            if method == "DELETE":
                fields['event'] = 'delete'

            data = models.Data(measurement=self.configuration.measurement,
                               fields=fields,
                               tags=tags)
            if data.fields:
                # Store the data in the latest data entry.
                data_layer.module_data[self.configuration.id].latest_data = data
                # Call the subsequent links.
                self._call_links(data)
        except Exception as e:
            self.logger.error("Something unexpected went wrong while trying to process the received request. {0}"
                              .format(str(e)), exc_info=config.EXC_INFO)

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        try:
            # Check if an id field exists.
            if "id" in data.fields:
                # Check if an object with the id is in the buffer.
                existing_object = next(
                    (x for x in self.circular_buffer if x.get("fields", {}).get("id", None) == data.fields.get("id")),
                    None)
                if existing_object is not None:
                    # Check if it has a delete event.
                    if "event" in data.fields:
                        if data.fields.get("event") == "delete":
                            # Delete the existing object.
                            self.circular_buffer.remove(existing_object)
                        else:
                            # Update the existing object.
                            self.circular_buffer.remove(existing_object)
                            self.circular_buffer.append(data.__dict__)
                    else:
                        # Update the existing object.
                        self.circular_buffer.remove(existing_object)
                        self.circular_buffer.append(data.__dict__)
                else:
                    # Create object.
                    self.circular_buffer.append(data.__dict__)
            else:
                # Create object.
                self.circular_buffer.append(data.__dict__)
        except Exception as e:
            self.logger.error("Something went wrong while trying to store data. {0}"
                              .format(str(e)),
                              exc_info=config.EXC_INFO)
        finally:
            # We return an empty object, so it will not be forwarded.
            return models.Data(measurement="",
                               fields={})
