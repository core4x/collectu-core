"""
**Note:**   This module can not be dynamically started. You have to restart (and automatically load) the complete app.
**Note:**   This output module does not support buffering. Only the last data changes are internally stored
            in a circular buffer of `buffer_size`.

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

#### Example Response

```json
{
   "error": false,
   "message": "Success",
   "data": "Optional information."
}
```

If we receive a field with `event: delete` and an `id` field is given, the object is removed.
If `id` field is given and the object already exists, the object is updated.
Otherwise, the object is added.
"""
import os
from threading import Thread
from dataclasses import dataclass, field
import json
import collections
import logging
from typing import Any, Tuple, Optional

# Internal imports.
import config
from modules.outputs.base.base import AbstractOutputModule, models


class ServerThread(Thread):
    """
    This is a thread class, which implements a shutdown method for stopping the server.

    :param app: The flask app.
    :param host: The host address.
    :param port: The port.
    :param name: The name of the thread.
    """

    def __init__(self, app, host: str, port, name: str):
        Thread.__init__(self, name="REST_Get_Output_Module_{0}".format(name), daemon=True)
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


class OutputModule(AbstractOutputModule):
    """
    Class for the console output module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module creates a RESTful HTTP endpoint for requesting data in json format."
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
    can_be_buffer: bool = False
    """If True, the child has to implement 'store_buffer_data' and 'get_buffer_data'."""

    @dataclass
    class Configuration(models.OutputModule):
        """
        The configuration model of the module.
        """
        path: str = field(
            metadata=dict(description="The path to the endpoint (e.g. `/path`) including `/`.",
                          required=False),
            default="/path")
        buffer_size: int = field(
            metadata=dict(description="The number of returned elements.",
                          required=False),
            default=100)
        host: str = field(
            metadata=dict(description="The host address of the endpoint.",
                          required=False),
            default="0.0.0.0")
        port: int = field(
            metadata=dict(description="The port of the endpoint.",
                          required=False),
            default=8124)
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

    def __init__(self, configuration: Configuration):
        # Calls the base init method.
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
        Just starts the thread for processing the queue.

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
            def verify_password(username, password) -> Optional[str]:
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
                    # Return empty username.
                    return ""

            @app.route('/<var>', methods=['GET'])
            @auth.login_required
            def endpoint(var) -> Optional[Tuple[Any, int]]:
                """
                Function gets called when request is send to server.

                :param var: The requested endpoint.

                :returns: A json object and a status code.
                """
                if "/" + var == self.configuration.path:
                    return json.dumps(list(self.circular_buffer), default=str), 200
                return flask.jsonify(error=True,
                                     message="Endpoint is not defined.",
                                     data=str("/" + var)), 404

            @app.errorhandler(werkzeug.exceptions.HTTPException)
            def handle_exception(e) -> Tuple[Any, int]:
                """
                Return JSON instead of HTML for HTTP errors.

                :param e: The occurred exception.
                """
                self.logger.error("Client '{0}' sent a request that this server could not understand "
                                  "('{1}' with status code: '{2}')."
                                  .format(str(flask.request.remote_addr), e.name, e.code))
                return flask.jsonify(error=True,
                                     message=e.name,
                                     data=e.description), 500

            self.server = ServerThread(app=app,
                                       host=self.configuration.host,
                                       port=self.configuration.port,
                                       name=self.configuration.id)
            self.server.start()

            # Start the queue processing for storing incoming data.
            Thread(target=self._process_queue,
                   daemon=False,
                   name="Queue_Worker_{0}".format(self.configuration.id)).start()

            self.logger.info("Successfully created REST endpoint on {0}."
                             .format(self.configuration.host + ":" + str(self.configuration.port) +
                                     self.configuration.path))
            return True

        except Exception as e:
            self.logger.critical("Something went wrong while trying to establish endpoint for '{0}{1}': {2}"
                                 .format(self.configuration.host + ":" + str(self.configuration.port),
                                         self.configuration.path, str(e)),
                                 exc_info=config.EXC_INFO)
            return False

    def stop(self):
        """
        Method for stopping the output module. Is called by the main thread.
        """
        if hasattr(self.server, 'shutdown'):
            self.server.shutdown()

    def _run(self, data: models.Data):
        """
        Method called when new data has to be processed.

        :param data: The data object to be processed.
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
