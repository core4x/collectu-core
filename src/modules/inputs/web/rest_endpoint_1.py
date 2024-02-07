"""
**Note:**   This module can not be dynamically started. You have to restart (and automatically load) the complete app.

**Note:**   When you want to use the REST endpoint input module inside docker,
            you have to specify the ports used in the configuration file also inside `docker-compose.yml`
            (e.g. `ports: - "8123:8123"`)
            When running in a container make the host address is `host: 0.0.0.0` in the configuration file.
            You can access the endpoints subsequently via `http://127.0.0.1:8123` or your machine ip.

The REST endpoint module returns responses in json format when receiving a request.

Possible status codes:

- 200: Success
- 404: Bad request
- 405: Method not allowed
- 500: Internal server error

#### Example Response

```json
{
   "error": false,
   "message": "Success",
   "data": "Optional information."
}
```

**Note:**   In the case for an unauthorized access, the response contains only a content body
            (response.content and not response.json()).

**Note:**   The client address, sending the post request is stored as tag `client` for variable modules.

If we receive a DELETE request, a field or tag (`event: delete`) is added.
If it is an POST or PUT request, the received data is forwarded without further adjustments.
"""
from dataclasses import dataclass, field
import os
from threading import Thread
from typing import Dict, Any, Optional, Tuple, Union, List
import logging
import json

# Internal imports.
import config
from modules.base.base import send_data
from modules.inputs.base.base import AbstractInputModule, AbstractVariableModule, AbstractTagModule, models
from models.validations import OneOf

__version__: str = "1.0"
"""The version of the module."""
__public__: bool = True
"""Is this module public?"""
__description__: str = "This module creates a webserver accepting HTTP requests (POST, PUT, and DELETE) and returns " \
                       "the received requests."
"""A short description."""
__author__: str = "Colin Reiff"
"""The author name."""
__email__: str = "colin.reiff@collectu.de"
"""The email address of the author."""
__deprecated__: bool = False
"""Is this module deprecated."""
__third_party_requirements__: list[str] = ["Werkzeug==2.0.2", "Flask-HTTPAuth==4.5.0", "Flask==2.0.2"]
"""Define your requirements here."""


class ServerThread(Thread):
    """
    This is a thread class, which implements a shutdown method for stopping the server.

    :param app: The flask app.
    :param host: The host address.
    :param port: The port.
    :param name: The name of the thread.
    """

    def __init__(self, app, host: str, port, name: str):
        Thread.__init__(self, name="REST_Post_Input_Module_{0}".format(name), daemon=True)
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


class InputModule(AbstractInputModule):
    """
    Class for the input module.

    :param configuration: The configuration object of the module.
    """
    version: str = __version__
    """The version of the module."""
    public: bool = __public__
    """Is this module public?"""
    description: str = "This module creates a webserver accepting HTTP requests (POST, PUT, and DELETE). " \
                       "This is the base and required for the according variable and tag modules."
    """A short description."""
    author: str = __author__
    """The author name."""
    email: str = __email__
    """The email address of the author."""
    deprecated: bool = __deprecated__
    """Is this module deprecated."""
    third_party_requirements: list[str] = __third_party_requirements__
    """Define your requirements here."""

    @dataclass
    class Configuration(models.InputModule):
        """
        The configuration model of the module.
        """
        host: str = field(
            metadata=dict(description="The host address of the server.",
                          required=False),
            default="0.0.0.0")
        port: int = field(
            metadata=dict(description="The port of the server.",
                          required=False),
            default=8123)
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

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)
        self.server = None
        """The werkzeug server."""
        self.registered_modules = {}
        """The variable and tag modules register themselves here with the path as key."""

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

            @app.route('/<var>', methods=['POST', 'PUT', 'DELETE'])
            @auth.login_required
            def endpoint(var) -> Optional[Tuple[dict, int]]:
                """
                Function gets called when request is send to server.

                :param var: The requested endpoint.

                :returns: A json object and a status code.
                """
                module = self.registered_modules.get("/" + var, None)
                if module is not None:
                    if flask.request.is_json:
                        if flask.request.method in module.configuration.methods:
                            module.view(body=flask.request.get_json(),
                                        client=flask.request.remote_addr,
                                        method=flask.request.method)
                            return flask.jsonify(error=False,
                                                 message="Successfully received input data.",
                                                 data=""), 200
                        else:
                            return flask.jsonify(error=True,
                                                 message="Request method is not allowed. "
                                                         "Please use one of the following: {0}."
                                                 .format(", ".join(module.configuration.methods)),
                                                 data=str("/" + var)), 400
                    else:
                        return flask.jsonify(error=True,
                                             message="Could not process input data. "
                                                     "Please only send json in the form of key value pairs.",
                                             data=str(flask.request.get_data())), 400
                else:
                    return flask.jsonify(error=True,
                                         message="Endpoint is not defined.",
                                         data=str("/" + var)), 404

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
        Method for stopping the module. Is called by the main thread.
        """
        if hasattr(self.server, 'shutdown'):
            self.server.shutdown()


class VariableModule(AbstractVariableModule):
    """
    A variable module.

    :param configuration: The configuration object of the module.
    :param input_module_instance: The instance of the parent input module if it exists.
    """
    version: str = __version__
    """The version of the module."""
    public: bool = __public__
    """Is this module public?"""
    description: str = "This module defines the specific path and accepted method on the HTTP REST server. " \
                       "It forwards the received request data."
    """A short description."""
    author: str = __author__
    """The author name."""
    email: str = __email__
    """The email address of the author."""
    deprecated: bool = __deprecated__
    """Is this module deprecated."""
    third_party_requirements: list[str] = __third_party_requirements__
    """Define your requirements here."""

    @dataclass
    class Configuration(models.VariableModule):
        """
        The configuration model of the module.
        """
        input_module: str = field(
            metadata=dict(description="The id of the input module. The required input module has to be "
                                      "module_name: inputs.web.rest_get_1",
                          required=True),
            default=None)
        path: str = field(
            metadata=dict(description="The path to the endpoint (e.g. `/path`) including `/`.",
                          required=True),
            default=None)
        methods: List[str] = field(
            metadata=dict(description="The allowed HTTP methods.",
                          required=False,
                          validate=OneOf(possibilities=['POST', 'DELETE', 'PUT'])),
            default_factory=lambda: ['POST', 'DELETE', 'PUT'])
        accept_all: bool = field(
            metadata=dict(description="If the json is a dict, we directly parse it into the fields. Otherwise, "
                                      "we only except the keys `fields` and `tags`.",
                          required=False),
            default=True)

    def __init__(self, configuration: Configuration, input_module_instance=None):
        super().__init__(configuration=configuration,
                         input_module_instance=input_module_instance)

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
            return True
        except Exception:
            raise ImportError("Could not import required packages. Please install '{0}'."
                              .format(' '.join(map(str, cls.third_party_requirements))))

    def start(self) -> bool:
        """
        Method for starting the module. Is called by the main thread.

        :returns: True if successfully started, otherwise false.
        """
        # Register in the input module.
        self.input_module_instance.registered_modules[self.configuration.path] = self
        return True

    def view(self, body: Union[dict, str], client: str, method: str):
        """
        Processes the received input_body.

        :param body: The input_body containing the fields, tags and measurement name to be stored.
        :param client: The client address of the request used for tagging.
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

            # Add a tag for the client, who send the data, if it doesn't exist.
            if 'client' not in tags:
                tags['client'] = client

            # If it is a DELETE method, we add an event field.
            if method == "DELETE":
                fields['event'] = 'delete'

            self._data_change(models.Data(measurement=self.configuration.measurement,
                                          fields=fields,
                                          tags=tags))

        except Exception as e:
            self.logger.error("Something unexpected went wrong while trying to process the received request. {0}"
                              .format(str(e)), exc_info=config.EXC_INFO)

    @send_data
    def _data_change(self, data: models.Data):
        """
        Send the data.
        """
        return data


class TagModule(AbstractTagModule):
    """
    A tag module.

    :param configuration: The configuration object of the module.
    :param input_module_instance: The instance of the parent input module if it exists.
    """
    version: str = __version__
    """The version of the module."""
    public: bool = __public__
    """Is this module public?"""
    description: str = "This module defines the specific path and accepted method on the HTTP REST server. " \
                       "It forwards the last received request data if requested."
    """A short description."""
    author: str = __author__
    """The author name."""
    email: str = __email__
    """The email address of the author."""
    deprecated: bool = __deprecated__
    """Is this module deprecated."""
    third_party_requirements: list[str] = __third_party_requirements__
    """Define your requirements here."""

    @dataclass
    class Configuration(models.TagModule):
        """
        The configuration model of the module.
        """
        input_module: str = field(
            metadata=dict(description="The id of the input module. The required input module has to be "
                                      "module_name: inputs.web.rest_get_1",
                          required=True),
            default=None)
        path: str = field(
            metadata=dict(description="The path to the endpoint (e.g. `/path`) including `/`.",
                          required=True),
            default=None)
        methods: List[str] = field(
            metadata=dict(description="The allowed HTTP methods.",
                          required=False,
                          validate=OneOf(possibilities=['POST', 'DELETE', 'PUT'])),
            default_factory=lambda: ['POST', 'DELETE', 'PUT'])
        accept_all: bool = field(
            metadata=dict(description="If the json is a dict, we directly parse it into the fields. Otherwise, "
                                      "we only except the keys `fields` and `tags`.",
                          required=False),
            default=True)

    def __init__(self, configuration: Configuration, input_module_instance=None):
        super().__init__(configuration=configuration,
                         input_module_instance=input_module_instance)
        # Register in the input module.
        self.input_module_instance.registered_modules[self.configuration.path] = self
        self.fields = {}
        """Contains the last received fields."""

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
            return True
        except Exception:
            raise ImportError("Could not import required packages. Please install '{0}'."
                              .format(' '.join(map(str, cls.third_party_requirements))))

    def view(self, body: Union[dict, str], client: str, method: str):
        """
        Processes the received input_body.

        :param body: The input_body containing the fields, tags and measurement name to be stored.
        :param client: The client address of the request used for tagging.
        :param method: The HTTP method. Can be POST, PUT, or DELETE.
        """
        try:
            # Convert json formatted string to dict if it isn't already a dict.
            if not isinstance(body, dict):
                body = json.loads(body)

            fields = {}
            if self.configuration.accept_all and isinstance(body, dict):
                fields = body
            elif isinstance(body, dict):
                for key, value in body.get('fields', {}).items():
                    fields[key] = value
            else:
                raise Exception("The received body is not a valid json dictionary: {0}".format(str(body)))

            # If it is a DELETE method, we add an event field.
            if method == "DELETE":
                fields['event'] = 'delete'

            self.fields = fields

        except Exception as e:
            self.logger.error("Something unexpected went wrong while trying to process the received request. {0}"
                              .format(str(e)), exc_info=config.EXC_INFO)

    def _run(self) -> Dict[str, Any]:
        """
        Method generates/requests the data for this module and returns it.

        :returns: A dict containing the generated key-value pairs.
        """
        return self.fields
