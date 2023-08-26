# -*- coding: UTF-8 -*-

import addonHandler
import os
import winsound
import controlTypes
import globalPluginHandler
import speech
import config
import ui
import scriptHandler
from scriptHandler import script
from globalCommands import SCRCAT_TOOLS, SCRCAT_CONFIG
from . import objdata

addonHandler.initTranslation()

#The part that turns off the role announcement is a huge hack, and might break. Set this to False to get rid of it
hook = True
loc = os.path.abspath(os.path.dirname(objdata.__file__))
old = None

def getPropertiesSpeech2(reason=controlTypes.OutputReason.QUERY, *args, **kwargs):
	role = kwargs.get('role', None)
	if 'role' in kwargs and role in sounds and os.path.exists(sounds[role]):
		del kwargs['role']
	return old(reason, *args, **kwargs)

def play(role):
	"""plays sound for role."""
	f = sounds[role]
	if os.path.exists(f):
		winsound.PlaySound(f, winsound.SND_ASYNC)

#Add all the roles, looking for name.wav.
sounds = {}
for role in [x for x in dir(controlTypes) if x.startswith('ROLE_')]:
	r = os.path.join(loc, role[5:].lower()+".wav")
	sounds[getattr(controlTypes, role)] = r
 
class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	def __init__(self, *args, **kwargs):
		globalPluginHandler.GlobalPlugin.__init__(self, *args, **kwargs)
		global old
		old = speech.getPropertiesSpeech
		if 'objsounds' not in config.conf:
			config.conf['objsounds'] = {"enabled": True}

	def event_gainFocus(self, obj, nextHandler):
		##huge hack. Why is configobj not saving the boolean as a boolean?
		if config.conf['objsounds']['enabled'] == u'False' or config.conf['objsounds']['enabled'] == False:
			nextHandler()
			return
		if hook:
			speech.getPropertiesSpeech = getPropertiesSpeech2
		play(obj.role)
		nextHandler()
		if hook:
			speech.getPropertiesSpeech = old

	@script(
		# Translators: Message presented in input help mode.
		description=_("Turns off obj sound"),
		category = SCRCAT_TOOLS,
		gesture="kb:NVDA+shift+delete"
	)
	def script_toggle(self, gesture):
		config.conf['objsounds']['enabled'] = not (str2bool(config.conf['objsounds']['enabled']))
		if config.conf['objsounds']['enabled']:
			ui.message(_("on"))
		else:
			ui.message(_("off"))

def str2bool(s):
	if s == 'True' or s == True: return True
	if s == 'False' or s == False: return False
