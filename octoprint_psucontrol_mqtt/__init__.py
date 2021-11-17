# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
import json

class PSUControl_MQTT(octoprint.plugin.StartupPlugin,
                      octoprint.plugin.RestartNeedingPlugin,
                      octoprint.plugin.TemplatePlugin,
                      octoprint.plugin.SettingsPlugin):

    def __init__(self):
        self.mqtt_publish = lambda *args, **kwargs: None
        self.mqtt_subscribe = lambda *args, **kwargs: None
        self.mqtt_unsubscribe = lambda *args, **kwargs: None

        self.config = dict()
        self.psu_status = None
        self.response_key = None
        self.response_on = None
        self.response_off = None

    def get_settings_defaults(self):
        return dict(
            control_topic="",
            state_topic="",
            on_command="ON",
            off_command="OFF",
            query_device_status=False,
            query_topic="",
            query_payload="",
            response_on="ON",
            response_off="OFF"
        )

    def reload_settings(self):
        for k, v in self.get_settings_defaults().items():
            if type(v) == bool:
                v = self._settings.get_boolean([k])
            else:
                v = self._settings.get([k])

            self.config[k] = v
            self._logger.debug("{}: {}".format(k, v))

    def on_after_startup(self):
        self.reload_settings()
        psucontrol_helpers = self._plugin_manager.get_helpers("psucontrol")
        if not psucontrol_helpers or 'register_plugin' not in psucontrol_helpers.keys():
            self._logger.warning("The version of PSUControl that is installed does not support plugin registration.")
            return

        self._logger.debug("Registering plugin with PSUControl")
        psucontrol_helpers['register_plugin'](self)

        mqtt_helpers = self._plugin_manager.get_helpers("mqtt", "mqtt_publish", "mqtt_subscribe", "mqtt_unsubscribe")
        if mqtt_helpers:
            if "mqtt_publish" in mqtt_helpers:
                self.mqtt_publish = mqtt_helpers["mqtt_publish"]
            if "mqtt_subscribe" in mqtt_helpers:
                self.mqtt_subscribe = mqtt_helpers["mqtt_subscribe"]
            if "mqtt_unsubscribe" in mqtt_helpers:
                self.mqtt_unsubscribe = mqtt_helpers["mqtt_unsubscribe"]
        else:
            self._logger.info("mqtt helpers not found..plugin won't work")
        
        self.parse_response_settings()

        try:
            self.mqtt_subscribe(self.config["state_topic"], self._on_mqtt_subscription)
            self._logger.debug("subscribing to: " + self.config["state_topic"])
        except ValueError:
            self._logger.error("State topic not set or invalid")
        
        if self.config["query_device_status"]:             
                self.mqtt_send(self.config["query_topic"], self.config["query_payload"])

    def turn_psu_on(self):
        self._logger.debug("Switching PSU On: sending command " + self.config["on_command"])
        self.mqtt_send(self.config["control_topic"], self.config["on_command"])
        if self.config["query_device_status"]:
            self.mqtt_send(self.config["query_topic"], self.config["query_payload"])

    def turn_psu_off(self):
        self._logger.debug("Switching PSU Off: sending command " + self.config["off_command"])
        self.mqtt_send(self.config["control_topic"], self.config["off_command"])
        if self.config["query_device_status"]:
            self.mqtt_send(self.config["query_topic"], self.config["query_payload"])

    def _on_mqtt_subscription(self, topic, message, retained=None, qos=None, *args, **kwargs):
        if topic == self.config["state_topic"]:
            self._logger.debug("received raw message: {message}".format(**locals()))
            message_parsed = self.parse_message(message)
            self._logger.debug("parsed incoming message to value: {message_parsed}".format(**locals()))

            if message_parsed.lower() == self.response_on.lower():
                self._logger.debug("received valid state for ON")
                self.psu_status = True
            elif message_parsed.lower() == self.response_off.lower():
                self.psu_status = False
                self._logger.debug("received valid state for OFF")
            else:
                self._logger.debug("Received unknown message. Assuming same PSU state as before")
                self._logger.debug("Valid messages are {self.response_on} and {self.response_off}".format(**locals()))

    def parse_response_settings(self):
        if str(self.config["response_on"]) == "" or str(self.config["response_off"]) == "":
            self._logger.error("Response settings (partly) empty. Aborting")
            return

        a = 0
        response_keys = [None, None]
        try:
            response_on_dict = json.loads(self.config["response_on"])
            self.response_on = str(list(response_on_dict.values())[0])
            response_keys[0] = list(response_on_dict.keys())[0]
            a += 1
        except (ValueError, AttributeError, TypeError):
            self.response_on = str(self.config["response_on"])
        try:
            response_off_dict = json.loads(self.config["response_off"])
            self.response_off = str(list(response_off_dict.values())[0])
            response_keys[1] = list(response_off_dict.keys())[0]
            a += 1
        except (ValueError, AttributeError, TypeError):
            self.response_off = str(self.config["response_off"])

        if a == 2:
            self.response_key = response_keys[0]
            if response_keys[0] != response_keys[1]:
                self._logger.warning("Response message settings have different json keys..50/50 chance")
        elif a == 1:
            self._logger.warning("Response message settings have mix of json and str..Should still work")
            for val in response_keys:
                if val is not None:
                    self.response_key = val
        else:  # a==0
            self.response_key = None
            # self.response_on = self.config["response_on"]
            # self.response_off = self.config["response_off"]

        self._logger.debug("response json key is " + str(self.response_key))

    def parse_message(self, message):
        message = message.decode("utf-8")
        try:
            message_dict = dict(json.loads(message))
        except (ValueError, TypeError):
            message_parsed = message  # message was no json, keep as is
            if self.response_key is not None:
                self._logger.warning("Response settings are json but incoming message is not..Should still work")
        else:
            message_parsed = message_dict.get(self.response_key)  # message is json, get value we are looking for
            if self.response_key is None:
                self._logger.error("Incoming message is json but response settings are not..Fix or this won't work")
        return str(message_parsed)

    def mqtt_send(self, topic, payload):
        try:
            self.mqtt_publish(topic, payload)
        except ValueError:
            self._logger.error("Query or command topic not set or invalid. Topic not updated.")

    def get_psu_state(self):
        if self.config["query_device_status"]:
            self.mqtt_send(self.config["query_topic"], self.config["query_payload"])
        return self.psu_status

    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        self.mqtt_unsubscribe(self.config["state_topic"])
        self._logger.debug("unsubscribing from: " + self.config["state_topic"])
        self.reload_settings()
        try:
            self.mqtt_subscribe(self.config["state_topic"], self._on_mqtt_subscription)
            self._logger.debug("subscribing to: " + self.config["state_topic"])
        except ValueError:
            self._logger.error("State topic not set or invalid")        
        self.parse_response_settings()

    def get_settings_version(self):
        return 1

    def on_settings_migrate(self, target, current=None):
        pass

    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=False)
        ]

    def get_update_information(self):
        return dict(
            psucontrol_mqttcontrol=dict(
                displayName="PSU Control - MQTT",
                displayVersion=self._plugin_version,
                type="github_release",
                user="oerkel47",
                repo="OctoPrint-PSUControl-MQTT",
                current=self._plugin_version,
                pip="https://github.com/oerkel47/OctoPrint-PSUControl-MQTT/archive/{target_version}.zip"
            )
        )


__plugin_name__ = "PSU Control - MQTT"
__plugin_pythoncompat__ = ">=3,<4"


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = PSUControl_MQTT()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }
