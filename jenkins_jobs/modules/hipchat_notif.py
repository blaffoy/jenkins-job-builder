# Copyright 2012 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""
Enable HipChat notifications of build execution.

:Parameters:
  * **enabled** *(bool)*: general cut off switch. If not explicitly set to
    ``true``, no hipchat parameters are written to XML. For Jenkins HipChat
    plugin of version prior to 0.1.5, also enables all build results to be
    reported in HipChat room. For later plugin versions, explicit notify-*
    setting is required (see below).
  * **room** *(str)*: name of HipChat room to post messages to

    .. deprecated:: 1.2.0  Please use 'rooms'.

  * **rooms** *(list)*: list of HipChat rooms to post messages to
  * **start-notify** *(bool)*: post messages about build start event
  * **notify-success** *(bool)*: post messages about successful build event
    (Jenkins HipChat plugin >= 0.1.5)
  * **notify-aborted** *(bool)*: post messages about aborted build event
    (Jenkins HipChat plugin >= 0.1.5)
  * **notify-not-built** *(bool)*: post messages about build set to NOT_BUILT
    status (Jenkins HipChat plugin >= 0.1.5). This status code is used in a
    multi-stage build (like maven2) where a problem in earlier stage prevented
    later stages from building.
  * **notify-unstable** *(bool)*: post messages about unstable build event
    (Jenkins HipChat plugin >= 0.1.5)
  * **notify-failure** *(bool)*:  post messages about build failure event
    (Jenkins HipChat plugin >= 0.1.5)
  * **notify-back-to-normal** *(bool)*: post messages about build being back to
    normal after being unstable or failed (Jenkins HipChat plugin >= 0.1.5)

Example:

.. literalinclude:: /../../tests/hipchat/fixtures/hipchat001.yaml
   :language: yaml

"""

# Enabling hipchat notifications on a job requires specifying the hipchat
# config in job properties, and adding the hipchat notifier to the job's
# publishers list.
# The publisher configuration contains extra details not specified per job:
#   - the hipchat authorisation token.
#   - the jenkins server url.
#   - a default room name/id.
# This complicates matters somewhat since the sensible place to store these
# details is in the global config file.
# The global config object is therefore passed down to the registry object,
# and this object is passed to the HipChat() class initialiser.

import xml.etree.ElementTree as XML
import jenkins_jobs.modules.base
import jenkins_jobs.errors
import logging
import pkg_resources
from six.moves import configparser
import sys

logger = logging.getLogger(__name__)


class HipChat(jenkins_jobs.modules.base.Base):
    sequence = 80

    def __init__(self, registry):
        self.authToken = None
        self.jenkinsUrl = None
        self.registry = registry

    def _load_global_data(self):
        """Load data from the global config object.
           This is done lazily to avoid looking up the '[hipchat]' section
           unless actually required.
        """
        if(not self.authToken):
            try:
                self.authToken = self.registry.global_config.get(
                    'hipchat', 'authtoken')
                # Require that the authtoken is non-null
                if self.authToken == '':
                    raise jenkins_jobs.errors.JenkinsJobsException(
                        "Hipchat authtoken must not be a blank string")
            except (configparser.NoSectionError,
                    jenkins_jobs.errors.JenkinsJobsException) as e:
                logger.fatal("The configuration file needs a hipchat section" +
                             " containing authtoken:\n{0}".format(e))
                sys.exit(1)
            self.jenkinsUrl = self.registry.global_config.get('jenkins', 'url')
            self.sendAs = self.registry.global_config.get('hipchat', 'send-as')

    def gen_xml(self, parser, xml_parent, data):
        hipchat = data.get('hipchat')
        if not hipchat or not hipchat.get('enabled', True):
            return
        self._load_global_data()

        properties = xml_parent.find('properties')
        if properties is None:
            properties = XML.SubElement(xml_parent, 'properties')
        pdefhip = XML.SubElement(properties,
                                 'jenkins.plugins.hipchat.'
                                 'HipChatNotifier_-HipChatJobProperty')

        room = XML.SubElement(pdefhip, 'room')
        if 'rooms' in hipchat:
            room.text = ",".join(hipchat['rooms'])
        elif 'room' in hipchat:
            logger.warn("'room' is deprecated, please use 'rooms'")
            room.text = hipchat['room']
        else:
            raise jenkins_jobs.errors.YAMLFormatError(
                "Must specify either 'room' or 'rooms' in hipchat config.")

        publishers = xml_parent.find('publishers')
        if publishers is None:
            publishers = XML.SubElement(xml_parent, 'publishers')
        hippub = XML.SubElement(publishers,
                                'jenkins.plugins.hipchat.HipChatNotifier')

        def translate_to_xml(parent, source, target, optional=True):
            if not optional or hipchat.get(source):
                XML.SubElement(parent, target).text = str(
                    hipchat.get(source, False)
                ).lower()

        yaml2xmlkeys = {
            'start-notify': ('startNotification', False),
            'notify-success': ('notifySuccess', True),
            'notify-aborted': ('notifyAborted', True),
            'notify-not-built': ('notifyNotBuilt', True),
            'notify-unstable': ('notifyUnstable', True),
            'notify-failure': ('notifyFailure', True),
            'notify-back-to-normal': ('notifyBackToNormal', True)
        }

        for xmlparent in [hippub, pdefhip]:
            for yamlkey, xmlkey in yaml2xmlkeys.items():
                xmloptional = xmlkey[1]
                xmlkey = xmlkey[0]
                translate_to_xml(xmlparent, yamlkey, xmlkey, xmloptional)

        plugin_info = self.registry.get_plugin_info("Jenkins HipChat Plugin")
        version = pkg_resources.parse_version(plugin_info.get('version', '0'))

        if version >= pkg_resources.parse_version("0.1.8"):
            XML.SubElement(hippub, 'buildServerUrl').text = self.jenkinsUrl
            XML.SubElement(hippub, 'sendAs').text = self.sendAs
        else:
            XML.SubElement(hippub, 'jenkinsUrl').text = self.jenkinsUrl

        XML.SubElement(hippub, 'authToken').text = self.authToken
        # The room specified here is the default room.  The default is
        # redundant in this case since a room must be specified.  Leave empty.
        XML.SubElement(hippub, 'room').text = room.text
