import http.client
import json
import logging
import threading
import urllib.parse
from datetime import datetime

from http.client import HTTPConnection
from typing import Optional


class BootAdminRegistrationHandler:

    def __init__(
            self,
            registration_url: str,
            application_name: str,
            pyctuator_base_url: str,
            start_time: datetime,
            service_url: str,
            registration_interval_sec: int,
    ) -> None:
        self.registration_url = registration_url
        self.application_name = application_name
        self.pyctuator_base_url = pyctuator_base_url
        self.start_time = start_time
        self.service_url = service_url
        self.registration_interval_sec = registration_interval_sec

        self.should_continue_registration_schedule: bool = True

    def _schedule_next_registration(
            self,
            registration_interval_sec: int
    ) -> None:
        timer = threading.Timer(
            registration_interval_sec,
            self._register_with_admin_server,
            []
        )
        timer.setDaemon(True)
        timer.start()

    def _register_with_admin_server(self) -> None:
        registration_data = {
            "name": self.application_name,
            "managementUrl": self.pyctuator_base_url,
            "healthUrl": f"{self.pyctuator_base_url}/health",
            "serviceUrl": self.service_url,
            "metadata": {"startup": self.start_time.isoformat()}
        }

        logging.debug("Trying to post registration data to %s: %s", self.registration_url, registration_data)

        conn: Optional[HTTPConnection] = None
        try:
            reg_url_split = urllib.parse.urlsplit(self.registration_url)
            conn = http.client.HTTPConnection(reg_url_split.hostname, reg_url_split.port)
            conn.request(
                "POST",
                reg_url_split.path,
                body=json.dumps(registration_data),
                headers={"Content-type": "application/json"})
            response = conn.getresponse()

            if response.status < 200 or response.status >= 300:
                logging.warning("Failed registering with boot-admin, got %s - %s", response.status, response.read())

        except Exception as e:  # pylint: disable=broad-except
            logging.warning("Failed registering with boot-admin, %s (%s)", e, type(e))

        finally:
            if conn:
                conn.close()

        # Schedule the next registration unless asked to abort
        if self.should_continue_registration_schedule:
            self._schedule_next_registration(self.registration_interval_sec)
        else:
            # Signal that the loop is stopped and we are ready for startup again
            self.should_continue_registration_schedule = True

    def start(self) -> None:
        logging.info("Starting recurring registration of %s with %s",
                     self.pyctuator_base_url, self.registration_url)
        self.should_continue_registration_schedule = True
        self._register_with_admin_server()

    def stop(self) -> None:
        logging.info("Stopping recurring registration")
        self.should_continue_registration_schedule = False
