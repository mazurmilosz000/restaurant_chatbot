import json
import logging
import re
from typing import Any, Text, Dict, List
from datetime import datetime, timedelta
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, EventType

logger = logging.getLogger()

# Load data from JSON files
def load_menu():
    with open("./menu.json", "r") as file:
        return json.load(file)["items"]

def load_opening_hours():
    with open("./opening_hours.json", "r") as file:
        return json.load(file)["items"]

class ActionCheckIfOpen(Action):
    def name(self) -> Text:
        return "action_check_if_open"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        opening_hours = load_opening_hours()
        day = tracker.get_slot("day")
        time = tracker.get_slot("time")

        # Validate the `day` slot
        if not day:
            dispatcher.utter_message(text="Could you specify the day you want to check?")
            return []

        day_hours = opening_hours.get(day.capitalize())
        if not day_hours:
            dispatcher.utter_message(text=f"We are closed on {day}.")
            return []

        open_time = day_hours["open"]
        close_time = day_hours["close"]
        is_close = close_time == 0 and open_time == 0
        logger.info(time)
        logger.info(day)
        try:
            if time is not None:
                user_time = datetime.strptime(time, "%I %p").hour
                if not is_close and open_time <= user_time < close_time:
                    dispatcher.utter_message(text=f"Yes, we are open on {day} at {time}.")
                else:
                    dispatcher.utter_message(text=f"Sorry, we are closed on {day} at {time}.")
            else:
                if not is_close:
                    dispatcher.utter_message(text=f"We are open on {day} from {open_time} to {close_time}")
                else:
                    dispatcher.utter_message(text=f"We are closed on {day}")
        except ValueError:
            dispatcher.utter_message(text="I couldn't understand the time format. Please try again.")

        return []

class ActionCheckOpeningHours(Action):
    def name(self) -> Text:
        return "action_check_opening_hours"

    def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: "Tracker",
            domain: "DomainDict"
    ) -> List[EventType]:
        # Load opening hours from the JSON file
        opening_hours = load_opening_hours()

        # Format the opening hours into a readable string
        hours_message = "\n".join(
            f"{day}: {hours['open']} AM to {hours['close']} PM"
            if hours['open'] > 0 or hours['close'] > 0
            else f"{day}: Closed"
            for day, hours in opening_hours.items()
        )

        # Send the message to the user
        dispatcher.utter_message(text=f"Our opening hours are:\n{hours_message}")

        return []

class ActionListMenuItems(Action):
    def name(self) -> Text:
        return "action_list_menu_items"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        menu = load_menu()
        menu_text = "\n".join([f"- {item['name']} (${item['price']})" for item in menu])
        dispatcher.utter_message(text=f"Our menu includes:\n{menu_text}")
        return []

class ActionPlaceOrder(Action):
    def name(self) -> Text:
        return "action_place_order"

    @staticmethod
    def normalize_string(s):
        # Remove spaces and hyphens
        return re.sub(r'[^a-zA-Z0-9]', '', s).lower()

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        menu = load_menu()
        item = next(tracker.get_latest_entity_values("item"), None)
        modification = tracker.get_slot("modification")

        order_message = "Sorry, I couldn't process your request."

        if not item:
            dispatcher.utter_message(text=f"Debug: item = {item}")
            dispatcher.utter_message(text="What would you like to order?")
            return []

        menu_item = next(
            (menu_item for menu_item in menu
             if self.normalize_string(menu_item["name"]) == self.normalize_string(item)),
            None
        )
        if menu_item:
            order_message = f"Your order for {menu_item['name']} (${menu_item['price']})"
            if modification:
                order_message += f" with {modification}"
            order_message += " has been placed."
            preparation_time = menu_item["preparation_time"]

            now = datetime.now()
            ready_time = now + timedelta(hours=preparation_time)
            ready_time_str = ready_time.strftime("%I:%M %p")
            order_message += f" Your order will be ready for pickup at {ready_time_str}."
        else:
            dispatcher.utter_message(text=f"I am so sorry we don't have {item} in our menu.")

        dispatcher.utter_message(text=order_message)
        return []

class ActionConfirmPickupTime(Action):
    def name(self) -> Text:
        return "action_confirm_pickup_time"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        preparation_time = tracker.get_slot("preparation_time") or 0.5
        now = datetime.now()
        ready_time = now + timedelta(hours=preparation_time)
        ready_time_str = ready_time.strftime("%I:%M %p")
        dispatcher.utter_message(text=f"Your order will be ready for pickup at {ready_time_str}.")
        return []

class ActionProvideDeliveryAddress(Action):
    def name(self) -> Text:
        return "action_provide_delivery_address"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        address = tracker.get_slot("address")
        if not address:
            dispatcher.utter_message(text="Could you please provide your delivery address?")
            return []

        dispatcher.utter_message(text=f"Thank you! Your order will be delivered to {address}.")
        return [SlotSet("address", address)]