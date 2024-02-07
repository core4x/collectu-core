"""
When using your email account, you probably have to change some settings to allow this module to access your account.
For example for gmail you have to enable "Allow access from less secure apps" in the settings.
"""
from dataclasses import dataclass, field
from threading import Thread
import smtplib
import ssl
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Internal imports.
import config
from modules.processors.base.base import AbstractProcessorModule, models


class ProcessorModule(AbstractProcessorModule):
    """
    A processor module.

    :param configuration: The configuration object of the module.
    """
    version: str = "1.0"
    """The version of the module."""
    public: bool = True
    """Is this module public?"""
    description: str = "This module sends emails to a given recipient using an email account."
    """A short description."""
    author: str = "Colin Reiff"
    """The author name."""
    email: str = "colin.reiff@collectu.de"
    """The email address of the author."""
    deprecated: bool = False
    """Is this module deprecated."""
    third_party_requirements: list[str] = []
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
        receiver: str = field(
            metadata=dict(description="The email address of the receiver.",
                          required=True,
                          dynamic=True),
            default=None)
        sender: str = field(
            metadata=dict(description="The email address of the sender.",
                          required=True,
                          dynamic=True),
            default=None)
        password: str = field(
            metadata=dict(description="The password of the sender (smtp server).",
                          required=True,
                          dynamic=True),
            default=None)
        smtp_host: str = field(
            metadata=dict(description="The smtp host address for sending the email.",
                          required=False,
                          dynamic=True),
            default="smtp.gmail.com")
        smtp_port: int = field(
            metadata=dict(description="The port of the smtp server.",
                          required=False,
                          dynamic=True),
            default=587)
        subject: str = field(
            metadata=dict(description="Subject of the email. Complete subject will be: "
                                      "`{config.APP_NAME}: Notification`.",
                          required=False,
                          dynamic=True),
            default="Notification")
        user_message: str = field(
            metadata=dict(description="The custom message written in the body of the email.",
                          required=False,
                          dynamic=True),
            default="")

    def __init__(self, configuration: Configuration):
        super().__init__(configuration=configuration)

    def _run(self, data: models.Data) -> models.Data:
        """
        Method for executing the module.

        :param data: The data object.

        :returns: The data object after processing.
        """
        Thread(target=self._send_mail,
               args=(data,),
               name="Send_mail_{0}".format(str(uuid.uuid4()))).start()
        return data

    def _send_mail(self, data: models.Data):
        """
        Just sends the email.
        """
        try:
            # Create a secure SSL context.
            context = ssl.create_default_context()
            with smtplib.SMTP(str(self._dyn(self.configuration.smtp_host)),
                              int(self._dyn(self.configuration.smtp_port))) as server:
                server.starttls(context=context)
                server.login(user=self._dyn(self.configuration.sender), password=self._dyn(self.configuration.password))
                message = MIMEMultipart()
                message["Subject"] = config.APP_NAME + ": {0}".format(str(self._dyn(self.configuration.subject)))
                sender = str(self._dyn(self.configuration.sender))
                message["From"] = sender
                receiver = str(self._dyn(self.configuration.receiver))
                message["To"] = receiver

                # The body of the message.
                body = ""

                # Add the user message to the body.
                message_body = str(self._dyn(self.configuration.user_message))
                if message_body != "":
                    body += "Message:\n"
                    body += message_body + "\n\n"

                # Add the fields to the body.
                body += "Fields:\n"
                for key, value in data.fields.items():
                    body += "\n"
                    body += str(key) + ": " + str(value)

                # Add the tags to the body.
                body += "\n\nTags:\n"
                for key, value in data.tags.items():
                    body += "\n"
                    body += str(key) + ": " + str(value)

                message.attach(MIMEText(body, 'plain'))
                # Send the actual mail.
                server.sendmail(from_addr=sender,
                                to_addrs=receiver,
                                msg=message.as_string())

            self.logger.info("Successfully send email to {0}.".format(self.configuration.receiver))

        except Exception as e:
            # If something unexpected went wrong we catch it.
            self.logger.error("Could not send mail: {0}".format(str(e)), exc_info=config.EXC_INFO)
