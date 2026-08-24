from __future__ import annotations

from typing import Any, Optional

try:
	import cursorManager
except ImportError:
	cursorManager = None

try:
	from controlTypes import Role, State
except ImportError:
	Role = None
	State = None

try:
	import textInfos
except ImportError:
	textInfos = None

try:
	from treeInterceptorHandler import BrowseModeTreeInterceptor
except ImportError:
	try:
		from browseMode import BrowseModeTreeInterceptor
	except ImportError:
		BrowseModeTreeInterceptor = None

try:
	from logHandler import log
except ImportError:
	log = None

try:
	import vision
except ImportError:
	vision = None


class BrowseModeQuickNavInterceptor:
	def __init__(self, plugin_instance: Any) -> None:
		self.plugin = plugin_instance
		self.orig_quick_nav_script: Optional[Any] = None
		self.orig_caret_movement: Optional[Any] = None
		self._patched_script_ref: Optional[Any] = None
		self._patched_caret_ref: Optional[Any] = None

	def patch_caret_movement(self) -> None:
		if self._patched_caret_ref is not None:
			return
		if cursorManager is None:
			return

		self.orig_caret_movement = getattr(cursorManager.CursorManager, "_caretMovementScriptHelper", None)

		def patched_caret_movement(instance: Any, gesture: Any, unit: Any, *args: Any, **kwargs: Any) -> None:
			if self.orig_caret_movement is None:
				return

			try:
				old_info = instance.makeTextInfo(textInfos.POSITION_CARET) if textInfos is not None else None
			except Exception:
				old_info = None

			self.orig_caret_movement(instance, gesture, unit, *args, **kwargs)

			if not self.plugin.cfg_sounds:
				return

			if not self.plugin.role_section.get("arrowNavSounds", True):
				return

			try:
				new_info = instance.makeTextInfo(textInfos.POSITION_CARET) if textInfos is not None else None
			except Exception:
				return

			if old_info and new_info and old_info.compareEndPoints(new_info, "startToStart") == 0:
				return

			obj = self._get_object_at_caret(instance)
			if obj is None:
				return

			played = False
			states = getattr(obj, "states", None)
			if states and State is not None:
				for state in states:
					try:
						name = State(state).name.replace("_", "").lower()
					except (ValueError, AttributeError):
						continue
					if self.plugin._check_and_play_nav(name, obj):
						played = True
						break

			if not played and Role is not None:
				role = getattr(obj, "role", None)
				if role is not None:
					try:
						name = Role(role).name.replace("_", "").lower()
						self.plugin._check_and_play_nav(name, obj)
					except (ValueError, AttributeError):
						pass

		self._patched_caret_ref = patched_caret_movement
		setattr(cursorManager.CursorManager, "_caretMovementScriptHelper", patched_caret_movement)

	def patch_quick_nav(self) -> None:
		if self._patched_script_ref is not None:
			return
		if BrowseModeTreeInterceptor is None:
			return

		self.orig_quick_nav_script = getattr(BrowseModeTreeInterceptor, "_quickNavScript", None)

		def patched_quick_nav_script(
			instance: Any,
			gesture: Any,
			itemType: Any,
			direction: Any,
			errorMessage: Any,
			readUnit: Any,
			*args: Any,
			**kwargs: Any,
		) -> None:
			if self.orig_quick_nav_script is None:
				return

			if not self.plugin.cfg_sounds:
				self.orig_quick_nav_script(
					instance, gesture, itemType, direction, errorMessage, readUnit, *args, **kwargs
				)
				return

			try:
				selection = instance.selection
			except Exception:
				selection = None

			if not selection and textInfos is not None and hasattr(instance, "makeTextInfo"):
				try:
					selection = instance.makeTextInfo(textInfos.POSITION_CARET)
				except Exception:
					pass

			old_info = selection.copy() if selection else None

			self.orig_quick_nav_script(instance, gesture, itemType, direction, errorMessage, readUnit, *args, **kwargs)

			try:
				new_selection = instance.selection
			except Exception:
				new_selection = None

			if not new_selection and textInfos is not None and hasattr(instance, "makeTextInfo"):
				try:
					new_selection = instance.makeTextInfo(textInfos.POSITION_CARET)
				except Exception:
					pass

			if old_info and new_selection:
				if old_info.compareEndPoints(new_selection, "startToStart") != 0:
					self.plugin._check_and_play_nav(str(itemType).lower())

		self._patched_script_ref = patched_quick_nav_script
		setattr(BrowseModeTreeInterceptor, "_quickNavScript", patched_quick_nav_script)

	def patch(self) -> None:
		self.patch_quick_nav()
		self.patch_caret_movement()

	def _get_object_at_caret(self, instance: Any) -> Any:
		if hasattr(instance, "currentNVDAObject"):
			try:
				return instance.currentNVDAObject
			except Exception:
				pass

		if textInfos is not None and hasattr(instance, "makeTextInfo"):
			try:
				info = instance.makeTextInfo(textInfos.POSITION_CARET)
				return info.focusableNVDAObjectAtStart
			except Exception:
				pass

		return None

	def terminate(self) -> None:
		if BrowseModeTreeInterceptor is not None and self.orig_quick_nav_script and self._patched_script_ref:
			current_script = getattr(BrowseModeTreeInterceptor, "_quickNavScript", None)
			if current_script == self._patched_script_ref:
				setattr(BrowseModeTreeInterceptor, "_quickNavScript", self.orig_quick_nav_script)

		if cursorManager is not None and self.orig_caret_movement and self._patched_caret_ref:
			current_caret = getattr(cursorManager.CursorManager, "_caretMovementScriptHelper", None)
			if current_caret == self._patched_caret_ref:
				setattr(cursorManager.CursorManager, "_caretMovementScriptHelper", self.orig_caret_movement)


class BrowseModeMoveListener:
	def __init__(self, plugin_instance: Any) -> None:
		self.plugin = plugin_instance
		self._extension_point: Optional[Any] = None
		self._registered = False
		self._logged_errors: set[str] = set()
		self._fallback_interceptor: Optional[BrowseModeQuickNavInterceptor] = None
		# Container roles never get navigation sounds from the browse-mode path.
		# Guarded with getattr so partial/foreign Role implementations stay safe.
		self._ignored_roles = frozenset(
			filter(
				None,
				(getattr(Role, name, None) for name in ("DOCUMENT", "WINDOW", "PANE", "APPLICATION", "UNKNOWN")),
			),
		)

	def start(self) -> None:
		if self._fallback_interceptor is None:
			self._fallback_interceptor = BrowseModeQuickNavInterceptor(self.plugin)

		extension_point = self._get_extension_point()
		if extension_point is not None:
			if self._registered and self._extension_point is extension_point:
				return
			if self._registered:
				self.stop()
			try:
				extension_point.register(self._on_browse_mode_move)
				# The official extension point is the single dispatch path when
				# available; monkey-patches stay dormant (mutual exclusion).
				self._extension_point = extension_point
				self._registered = True
				return
			except Exception:
				self._log_exception_once("register", "Failed to register browse-mode move listener")

		# Fallback only: no usable post_browseModeMove on this NVDA build.
		try:
			self._fallback_interceptor.patch_caret_movement()
		except Exception:
			pass

		try:
			self._fallback_interceptor.patch_quick_nav()
		except Exception:
			pass

	def stop(self) -> None:
		if self._registered and self._extension_point is not None:
			try:
				self._extension_point.unregister(self._on_browse_mode_move)
			except Exception:
				self._log_exception_once("unregister", "Failed to unregister browse-mode move listener")
			self._registered = False
			self._extension_point = None

		if self._fallback_interceptor is not None:
			try:
				self._fallback_interceptor.terminate()
			except Exception:
				pass

	patch = start
	terminate = stop

	def _get_extension_point(self) -> Optional[Any]:
		if vision is None:
			return None
		handler = getattr(vision, "handler", None)
		extension_points = getattr(handler, "extensionPoints", None)
		return getattr(extension_points, "post_browseModeMove", None)

	def _on_browse_mode_move(self, *args: Any, **kwargs: Any) -> None:
		if not getattr(self.plugin, "cfg_sounds", False):
			return

		# The extension point cannot distinguish arrows from quick nav; this
		# setting therefore gates every browse-mode move sound. Without it the
		# checkbox would stay dead on modern NVDA, where only this path runs.
		role_section = getattr(self.plugin, "role_section", None)
		if role_section is not None and not role_section.get("arrowNavSounds", True):
			return

		cursor_manager = kwargs.get("obj")
		if cursor_manager is None and args:
			cursor_manager = args[0]
		if cursor_manager is None:
			return

		# Only browse-mode documents play navigation sounds here. Plain editable
		# text fields also use a CursorManager; their caret moves are already
		# covered by event_gainFocus.
		if BrowseModeTreeInterceptor is not None and not isinstance(cursor_manager, BrowseModeTreeInterceptor):
			return

		# Skip selection extensions (shift+arrows): sounds follow caret moves only.
		try:
			sel_info = cursor_manager.makeTextInfo(textInfos.POSITION_SELECTION) if textInfos is not None else None
		except Exception:
			sel_info = None
		if sel_info is not None and not getattr(sel_info, "isCollapsed", True):
			return

		try:
			nav_obj = self._get_object_at_caret(cursor_manager)
			if nav_obj is None or getattr(nav_obj, "role", None) in self._ignored_roles:
				return
			self.plugin._play_nav_for_object(nav_obj)
		except Exception:
			self._log_exception_once("dispatch", "Browse-mode navigation sound dispatch failed")

	def _get_object_at_caret(self, cursor_manager: Any) -> Any:
		if textInfos is not None and hasattr(cursor_manager, "makeTextInfo"):
			try:
				info = cursor_manager.makeTextInfo(textInfos.POSITION_CARET)
			except Exception:
				info = None
			if info is not None:
				for attr in ("NVDAObjectAtStart", "focusableNVDAObjectAtStart"):
					try:
						nav_obj = getattr(info, attr)
					except Exception:
						nav_obj = None
					if nav_obj is not None:
						return nav_obj

		try:
			return cursor_manager.currentNVDAObject
		except Exception:
			return None

	def _log_exception_once(self, key: str, message: str) -> None:
		if key in self._logged_errors:
			return
		self._logged_errors.add(key)
		if log is not None and hasattr(log, "exception"):
			log.exception(message)
