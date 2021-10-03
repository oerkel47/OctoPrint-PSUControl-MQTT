# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
# import json


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
            if type(v) == str:
                v = self._settings.get([k])
            elif type(v) == int:
                v = self._settings.get_int([k])
            elif type(v) == float:
                v = self._settings.get_float([k])
            elif type(v) == bool:
                v = self._settings.get_boolean([k])
        
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

        self.mqtt_subscribe(self.config["state_topic"], self.on_mqtt_subscription)
        self._logger.debug("Subscribing to {}", self.config["state_topic"])
        if self.config["query_device_status"]:
            self.mqtt_publish(self.config["query_topic"], self.config["query_payload"])

    def turn_psu_on(self):
        self._logger.debug("Switching PSU On")
        self.mqtt_publish(self.config["control_topic"], self.config["on_command"])

    def turn_psu_off(self):
        self._logger.debug("Switching PSU Off")
        self.mqtt_publish(self.config["control_topic"], self.config["off_command"])

    def on_mqtt_subscription(self, topic, message, retained=None, qos=None, *args, **kwargs):
        self._logger.debug("mqtt: received a message for Topic {topic}. Message: {message}".format(**locals()))
        self._logger.debug("Valid messages are " + self.config["response_on"] + " and " + self.config["response_off"])
        message = message.decode("utf-8")
        self._logger.debug("Message in utf-8: {message}".format(**locals()))

        if topic == self.config["state_topic"]:
            if message == self.config["response_on"]:
                self._logger.debug("received valid state: on")
                self.psu_status = True
            elif message == self.config["response_off"]:
                self.psu_status = False
                self._logger.debug("received valid state: off")
            else:
                self._logger.debug("unknown message and thus PSU status, not changing..")


    def get_psu_state(self):
        if self.config["query_device_status"]:
            self._logger.debug("Sending periodic query to get psu state")
            self.mqtt_publish(self.config["query_topic"], self.config["query_payload"])
        return self.psu_status

    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        self.mqtt_unsubscribe(self.config["state_topic"])
        self._logger.debug("unsubscribing from: " + self.config["state_topic"])
        self.reload_settings()
        self.mqtt_subscribe(self.config["state_topic"], self.on_mqtt_subscription)
        self._logger.debug("subscribing to: " + self.config["state_topic"])

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
