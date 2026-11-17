# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""Core Guardrails class for CXAS Scrapi."""

import typing
from typing import Any

from google.cloud.ces_v1beta import types
from google.protobuf import field_mask_pb2, json_format

from cxas_scrapi.core.apps import Apps
from cxas_scrapi.core.common import Common

_DEFAULT_DENY_RESPONSE = "I cannot help with that request."


class Guardrails(Apps):
    """Core Class for managing Guardrail Resources."""

    def __init__(
        self,
        app_name: str,
        creds_path: str | None = None,
        creds_dict: dict[str, str] | None = None,
        creds: Any = None,
        scope: list[str] | None = None,
        **kwargs: typing.Any,
    ) -> None:
        """Initializes the Guardrails client."""
        project_id = Common._get_project_id(app_name)
        location = Common._get_location(app_name)
        if not project_id or not location:
            raise ValueError(
                f"Invalid app_name format: {app_name}. "
                "Expected format: "
                "projects/<project>/locations/<location>/apps/<app>"
            )

        super().__init__(
            project_id=project_id,
            location=location,
            creds_path=creds_path,
            creds_dict=creds_dict,
            creds=creds,
            scope=scope,
            **kwargs,
        )
        self.resource_type = "guardrails"
        self.app_name = app_name

    def list_guardrails(self) -> list[types.Guardrail]:
        """Lists guardrails within a specific app."""
        request = types.ListGuardrailsRequest(parent=self.app_name)
        response = self.client.list_guardrails(request=request)
        return list(response)

    def get_guardrails_map(self, reverse: bool = False) -> dict[str, str]:
        """Creates a map of Guardrail full names to display names.

        Args:
            reverse: If True, map display_name -> name.
        """
        guardrails = self.list_guardrails()
        guardrails_dict: dict[str, str] = {}

        for guardrail in guardrails:
            display_name = guardrail.display_name
            name = guardrail.name
            if display_name and name:
                if reverse:
                    guardrails_dict[display_name] = name
                else:
                    guardrails_dict[name] = display_name
        return guardrails_dict

    def get_guardrail(self, guardrail_id: str) -> types.Guardrail:
        """Gets a specific guardrail."""
        request = types.GetGuardrailRequest(
            name=f"{self.app_name}/guardrails/{guardrail_id}"
        )
        return self.client.get_guardrail(request=request)

    @staticmethod
    def _normalize_trigger_action(
        action: types.TriggerAction | dict[str, Any] | str | None,
    ) -> types.TriggerAction:
        """Converts shorthand or dict actions into a ``types.TriggerAction``."""
        if action is None:
            return types.TriggerAction(
                respond_immediately=types.TriggerAction.RespondImmediately(
                    responses=[
                        types.TriggerAction.Response(
                            text=_DEFAULT_DENY_RESPONSE
                        )
                    ]
                )
            )
        if isinstance(action, types.TriggerAction):
            return action
        if isinstance(action, dict):
            try:
                return types.TriggerAction(**action)
            except (TypeError, ValueError):
                parsed = types.TriggerAction()
                json_format.ParseDict(action, parsed._pb)
                return parsed
        if isinstance(action, str):
            norm = action.strip().upper()
            if norm == "DENY":
                return types.TriggerAction(
                    respond_immediately=types.TriggerAction.RespondImmediately(
                        responses=[
                            types.TriggerAction.Response(
                                text=_DEFAULT_DENY_RESPONSE
                            )
                        ]
                    )
                )
            if norm == "GENERATIVE_ANSWER":
                return types.TriggerAction(
                    generative_answer=types.TriggerAction.GenerativeAnswer()
                )
            raise ValueError(
                f"Unsupported guardrail action '{action}'. Expected a "
                "TriggerAction, dict, 'DENY', 'GENERATIVE_ANSWER', or None."
            )
        raise TypeError(
            f"Unsupported guardrail action type: {type(action).__name__}"
        )

    def create_guardrail(
        self,
        guardrail_id: str,
        display_name: str,
        payload: dict[str, Any],
        action: types.TriggerAction | dict[str, Any] | str | None = None,
        description: str = "",
        enabled: bool = True,
    ) -> types.Guardrail:
        """Creates a new guardrail given a specific payload dictionary.

        The payload controls which of the 5 mutually exclusive guardrail
        types is instantiated (content_filter, llm_policy,
        llm_prompt_security, model_safety, code_callback).
        """
        payload_copy = dict(payload)
        payload_copy.pop("display_name", None)
        payload_copy.pop("description", None)
        payload_action = payload_copy.pop("action", None)
        effective_action = action if action is not None else payload_action

        guardrail = types.Guardrail(
            display_name=display_name,
            description=description,
            action=self._normalize_trigger_action(effective_action),
            enabled=enabled,
            **payload_copy,
        )

        request = types.CreateGuardrailRequest(
            parent=self.app_name, guardrail_id=guardrail_id, guardrail=guardrail
        )
        return self.client.create_guardrail(request=request)

    def update_guardrail(
        self, guardrail_id: str, **kwargs: typing.Any
    ) -> types.Guardrail:
        """Updates specific fields of an existing Guardrail."""
        guardrail = types.Guardrail(
            name=f"{self.app_name}/guardrails/{guardrail_id}"
        )
        mask_paths = []

        for key, value in kwargs.items():
            resolved_value = (
                self._normalize_trigger_action(value)
                if key == "action" and value is not None
                else value
            )
            setattr(guardrail, key, resolved_value)
            mask_paths.append(key)

        request = types.UpdateGuardrailRequest(
            guardrail=guardrail,
            update_mask=field_mask_pb2.FieldMask(paths=mask_paths),
        )
        return self.client.update_guardrail(request=request)

    def delete_guardrail(self, guardrail_id: str) -> None:
        """Deletes a specific guardrail."""
        request = types.DeleteGuardrailRequest(
            name=f"{self.app_name}/guardrails/{guardrail_id}"
        )
        self.client.delete_guardrail(request=request)
