import os
from pathlib import Path
from typing import Any, Callable
import webbrowser as web

import wx

import addonHandler
from gui import guiHelper
from gui.settingsDialogs import SettingsPanel
import ui


addonHandler.initTranslation()
_: Callable[[str], str]


class NavSettingsPanel(SettingsPanel):
    main_plugin: Any
    title = _("navigation sounds")

    def makeSettings(self, sizer: wx.Sizer) -> None:
        if self.main_plugin is None:
            raise ValueError("The plugin is not transferred to the settings panel")

        base_sounds_dir = self.main_plugin.main_paths / "effects"
        nav_sounds_dir = base_sounds_dir / "navsounds"
        type_sounds_dir = base_sounds_dir / "typingsound"
        nav_sounds = [p.name for p in nav_sounds_dir.iterdir() if p.is_dir()]
        type_sounds = [p.name for p in type_sounds_dir.iterdir() if p.is_dir()]

        sizer_helper = guiHelper.BoxSizerHelper(self, sizer=sizer)
        sizer_helper.addItem(wx.StaticText(
            self, label=_("select sound"), name="ts"
        ))

        self.sou = sizer_helper.addItem(wx.Choice(self, name="ts"))
        self.sou.Set(nav_sounds)
        self.sou.SetStringSelection(self.main_plugin.role_section["soundType"])

        self.nar = sizer_helper.addItem(wx.CheckBox(self, label=_("say roles")))
        self.nar.SetValue(self.main_plugin.role_section["sayRoles"])

        self.nas = sizer_helper.addItem(wx.CheckBox(self, label=_("say states")))
        self.nas.SetValue(self.main_plugin.role_section["sayStates"])

        self.nab = sizer_helper.addItem(wx.CheckBox(self, label=_("navigation sounds")))
        self.nab.SetValue(self.main_plugin.role_section["cfgSounds"])

        self.ts = sizer_helper.addItem(wx.CheckBox(self, label=_("keyboard typing sound")))
        self.ts.SetValue(self.main_plugin.role_section["typing"])

        self.edit = sizer_helper.addItem(wx.CheckBox(self, label=_("enable typing sound in text boxes only")))
        self.edit.SetValue(self.main_plugin.role_section["edit"])

        sizer_helper.addItem(wx.StaticText(
            self, label=_("select typing sound"), name="tt"
        ))

        self.sou1 = sizer_helper.addItem(wx.Choice(self, name="tt"))
        self.sou1.Set(type_sounds)
        self.sou1.SetStringSelection(self.main_plugin.role_section["type"])

        sizer_helper.addItem(
            wx.StaticText(self, label=_("volume"), name="tt2")
        )
        self.sou2 = sizer_helper.addItem(wx.SpinCtrl(self, name="tt2", min=0, max=100))
        self.sou2.SetValue(self.main_plugin.role_section["volume"])

        b = sizer_helper.addItem(wx.Button(self, label=_("open sounds folder")))
        b.Bind(wx.EVT_BUTTON, self.onopen)
        donate = sizer_helper.addItem(wx.Button(self, label=_("donate")))
        donate.Bind(wx.EVT_BUTTON, self.ondonate)

    def postInit(self) -> None:
        self.sou.SetFocus()

    def onopen(self, _: wx.Event) -> None:
        effects_path = Path(__file__).resolve().parent / "effects"
        os.startfile(effects_path)

    def onSave(self) -> None:
        if self.main_plugin is None:
            raise ValueError("The plugin is not transferred to the settings panel")

        self.main_plugin.role_section["soundType"] = self.sou.GetStringSelection()
        self.main_plugin.role_section["sayRoles"] = self.nar.GetValue()
        self.main_plugin.say_roles = self.main_plugin.role_section["sayRoles"]

        self.main_plugin.role_section["sayStates"] = self.nas.GetValue()
        self.main_plugin.say_states = self.main_plugin.role_section["sayStates"]

        self.main_plugin.role_section["cfgSounds"] = self.nab.GetValue()
        self.main_plugin.cfg_sounds = self.main_plugin.role_section["cfgSounds"]

        self.main_plugin.role_section["typing"] = self.ts.GetValue()
        self.main_plugin.role_section["edit"] = self.edit.GetValue()
        self.main_plugin.role_section["type"] = self.sou1.GetStringSelection()
        self.main_plugin.role_section["volume"] = self.sou2.GetValue()

        self.main_plugin.reload_audio()
        self.main_plugin.audio_manager.update_volume(self.main_plugin.role_section["volume"])

    def ondonate(self, _: wx.Event) -> None:
        ui.message("please wait")
        web.open("https://www.paypal.me/ahmedthebest31")
        ui.message("donation link is opened")
