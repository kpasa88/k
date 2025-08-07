#!/usr/bin/env python3
import os
import sys
import random
import textwrap
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


def wrap(text: str, width: int = 78) -> str:
    return "\n".join(textwrap.wrap(text, width=width))


def prompt(prompt_text: str) -> str:
    try:
        return input(prompt_text)
    except EOFError:
        return ""


@dataclass
class Perishable:
    name: str
    quantity: int
    days_until_spoil: int


@dataclass
class Inventory:
    water_units: int = 6  # 1 unit ~= 1 liter
    food_rations: int = 4  # shelf-stable rations
    fresh_meat: List[Perishable] = field(default_factory=list)  # perishable
    jerky: int = 0  # preserved meat
    ammo_rounds: int = 10
    medkits: int = 1
    fuel_gallons: float = 2.0
    firewood: int = 0
    fishing_kit: bool = False
    radio: bool = True

    def total_food_units(self) -> int:
        return self.food_rations + self.jerky + sum(p.quantity for p in self.fresh_meat)


@dataclass
class Player:
    name: str
    health: int = 100
    stamina: int = 100
    morale: int = 70
    hunting_skill: int = 40
    fishing_skill: int = 20
    foraging_skill: int = 35
    stealth_skill: int = 30
    inventory: Inventory = field(default_factory=Inventory)

    def is_alive(self) -> bool:
        return self.health > 0


@dataclass
class Location:
    key: str
    name: str
    description: str
    has_hunting: bool
    has_fishing: bool
    special: Optional[str] = None


class World:
    def __init__(self) -> None:
        self.locations: Dict[str, Location] = {
            "new_braunfels": Location(
                key="new_braunfels",
                name="New Braunfels",
                description=(
                    "The Comal and Guadalupe rivers cut through town. H-E-Bs sit dark, and the "
                    "hum of I-35 is quieter than it should be. Neighborhoods are still."
                ),
                has_hunting=True,
                has_fishing=True,  # rivers exist, though fishing is hit-or-miss
                special="start",
            ),
            "austin": Location(
                key="austin",
                name="Austin",
                description=(
                    "The city sprawls under silent high-rises. Streets feel watched, but "
                    "deserted. The Colorado River winds through, offering water if you can "
                    "make it safe."
                ),
                has_hunting=False,
                has_fishing=True,
            ),
            "houston": Location(
                key="houston",
                name="Houston",
                description=(
                    "Endless neighborhoods and highways. Supplies exist, scattered and risky. "
                    "Humidity presses close; you sweat more just standing still."
                ),
                has_hunting=False,
                has_fishing=True,
            ),
            "schulenburg": Location(
                key="schulenburg",
                name="Schulenburg",
                description=(
                    "Family land east: an acre with a small pond, a shed, maybe tools. It feels "
                    "like a plan—if you can reach it."
                ),
                has_hunting=True,
                has_fishing=True,
                special="family_land",
            ),
        }
        # Approximate road distances (miles) from each node
        self.distances_miles: Dict[Tuple[str, str], int] = {}
        self._set_distance("new_braunfels", "austin", 50)
        self._set_distance("new_braunfels", "schulenburg", 95)
        self._set_distance("new_braunfels", "houston", 175)
        self._set_distance("austin", "schulenburg", 70)
        self._set_distance("austin", "houston", 165)
        self._set_distance("schulenburg", "houston", 95)

    def _set_distance(self, a: str, b: str, miles: int) -> None:
        self.distances_miles[(a, b)] = miles
        self.distances_miles[(b, a)] = miles

    def get_neighbors(self, location_key: str) -> List[Tuple[str, int]]:
        neighbors: List[Tuple[str, int]] = []
        for (a, b), miles in self.distances_miles.items():
            if a == location_key:
                neighbors.append((b, miles))
        return neighbors


class Game:
    def __init__(self, demo_mode: bool = False) -> None:
        self.world = World()
        self.player = Player(name="You")
        self.current_location_key: str = "new_braunfels"
        # The outage began three days ago; game begins Day 4
        self.day: int = 4
        self.hour: int = 8  # morning
        self.temperature_f: int = 92
        self.demo_mode = demo_mode
        self.random_seed = None

    # ------------- Narrative -------------
    def show_intro(self) -> None:
        intro = (
            "Day 4. New Braunfels. The power died three nights ago and never came back. "
            "Cell towers stuttered, then fell silent. Internet: gone. Your radio blinks to life "
            "in bursts—voices arguing, warnings, dead air. No one knows why. Only that it "
            "hasn’t ended."
        )
        print("\n" + wrap(intro))
        print()
        print(wrap(
            "You listen to the radio. Stations carry rumor like wind carries cedar. A voice "
            "says: 'Stay calm. Boil water. Avoid highways at night.' Another insists it’s a "
            "software glitch. Another: 'We’re fine. It’s over.' But there’s only quiet behind "
            "them."
        ))
        print()
        print(wrap(
            "Your supplies won’t last long. There’s family out in Schulenburg—an acre and a "
            "small pond. If you can reach it, you might bend this chaos into a plan. Or "
            "maybe you carve out a life here, moving carefully, learning the flows of a "
            "quieter world."
        ))
        print()

    # ------------- Time and Conditions -------------
    def advance_time(self, hours: int) -> None:
        for _ in range(hours):
            self.hour += 1
            if self.hour >= 24:
                self.hour = 0
                self.day += 1
                self.on_new_day()

    def on_new_day(self) -> None:
        self.temperature_f = random.randint(85, 103)
        self.apply_daily_needs()
        self.resolve_spoilage()
        self.random_daily_event()

    def apply_daily_needs(self) -> None:
        # Heat increases water need
        base_water_need = 2
        if self.temperature_f >= 95:
            base_water_need += 1
        water_to_consume = min(base_water_need, self.player.inventory.water_units)
        self.player.inventory.water_units -= water_to_consume
        if water_to_consume < base_water_need:
            self.player.health -= 5
            self.player.stamina -= 10
            self.player.morale -= 5
        # Food
        base_food_need = 1
        food_available = self.consume_food_units(base_food_need)
        if food_available < base_food_need:
            self.player.health -= 5
            self.player.stamina -= 10
            self.player.morale -= 3
        self.player.health = max(0, min(self.player.health, 100))
        self.player.stamina = max(0, min(self.player.stamina, 100))
        self.player.morale = max(0, min(self.player.morale, 100))

    def consume_food_units(self, units_needed: int) -> int:
        consumed = 0
        # Eat shelf-stable rations first
        while units_needed > 0 and self.player.inventory.food_rations > 0:
            self.player.inventory.food_rations -= 1
            units_needed -= 1
            consumed += 1
        # Then jerky
        while units_needed > 0 and self.player.inventory.jerky > 0:
            self.player.inventory.jerky -= 1
            units_needed -= 1
            consumed += 1
        # Then fresh meat
        while units_needed > 0 and sum(p.quantity for p in self.player.inventory.fresh_meat) > 0:
            for p in self.player.inventory.fresh_meat:
                if p.quantity > 0:
                    p.quantity -= 1
                    units_needed -= 1
                    consumed += 1
                    break
            # remove empty entries
            self.player.inventory.fresh_meat = [x for x in self.player.inventory.fresh_meat if x.quantity > 0]
        return consumed

    def resolve_spoilage(self) -> None:
        for p in self.player.inventory.fresh_meat:
            p.days_until_spoil -= 1
        spoiled = [p for p in self.player.inventory.fresh_meat if p.days_until_spoil <= 0]
        if spoiled:
            lost = sum(p.quantity for p in spoiled)
            self.player.inventory.fresh_meat = [p for p in self.player.inventory.fresh_meat if p.days_until_spoil > 0]
            print(wrap(f"Some fresh meat spoiled: lost {lost} units."))

    # ------------- Events -------------
    def random_daily_event(self) -> None:
        # Occasional radio snippet or ambient event
        if random.random() < 0.4 and self.player.inventory.radio:
            snippet = random.choice([
                "A calm voice: 'Report rolling outages nationwide. Infrastructure teams are... ' static. silence.",
                "Two hosts argue about solar flares and firmware. Someone laughs like it matters.",
                "A county official: 'Boil water. Share what you can. Check on your neighbors.'",
                "A clipped warning: 'Avoid I-10 at night. Reports of roadside robberies.'",
                "Static, then music—half a song from twenty years ago—then silence again.",
            ])
            print(wrap(f"Radio: {snippet}"))

    # ------------- Actions -------------
    def action_scavenge(self) -> None:
        print(wrap("You move quietly, searching for what the outage left loose."))
        self.advance_time(2)
        self.player.stamina = max(0, self.player.stamina - random.randint(5, 15))
        find_roll = random.random()
        if find_roll < 0.25:
            found = random.randint(1, 3)
            self.player.inventory.water_units += found
            print(wrap(f"You found bottled water: {found} units."))
        elif find_roll < 0.47:
            found = random.randint(1, 2)
            self.player.inventory.food_rations += found
            print(wrap(f"You found shelf-stable food: {found} rations."))
        elif find_roll < 0.64:
            fuel = round(random.uniform(0.5, 2.0), 1)
            self.player.inventory.fuel_gallons += fuel
            print(wrap(f"You siphoned fuel: {fuel} gallons."))
        elif find_roll < 0.76:
            ammo = random.randint(2, 6)
            self.player.inventory.ammo_rounds += ammo
            print(wrap(f"You found ammo: +{ammo} rounds."))
        elif find_roll < 0.85:
            self.player.inventory.medkits += 1
            print(wrap("You found a medkit."))
        elif find_roll < 0.93:
            self.player.inventory.firewood += 2
            print(wrap("You collected usable firewood."))
        else:
            print(wrap("You found little that helps today."))

        # Risk
        if random.random() < 0.2:
            self.handle_incident()

    def action_hunt(self) -> None:
        location = self.world.locations[self.current_location_key]
        if not location.has_hunting:
            print(wrap("This area doesn’t lend itself to hunting. You’d just scare everything off."))
            return
        if self.player.inventory.ammo_rounds <= 0:
            print(wrap("You have no ammo."))
            return
        print(wrap("You skirt the edges of town, following trails and fence lines."))
        self.advance_time(3)
        self.player.inventory.ammo_rounds -= 1
        hunt_chance = (self.player.hunting_skill + self.player.stealth_skill) / 200.0
        hunt_chance += 0.1  # Texas Hill Country is forgiving
        if random.random() < hunt_chance:
            meat_units = random.randint(2, 5)
            self.player.inventory.fresh_meat.append(Perishable("fresh_meat", meat_units, 2))
            print(wrap(f"A clean shot. You dress the game and carry back {meat_units} units of fresh meat."))
        else:
            print(wrap("Tracks, wind, and noise. Today, the brush stays quiet."))
        if random.random() < 0.15:
            self.handle_incident()

    def action_fish(self) -> None:
        location = self.world.locations[self.current_location_key]
        if not location.has_fishing:
            print(wrap("No viable fishing here."))
            return
        print(wrap("You work a quiet bank, line whispering against the guides."))
        self.advance_time(2)
        base = self.player.fishing_skill / 100.0
        if location.key == "schulenburg":
            base += 0.2  # Family pond advantage
        if random.random() < base:
            fish = random.randint(1, 3)
            self.player.inventory.fresh_meat.append(Perishable("fish", fish, 1))
            print(wrap(f"You catch {fish} fish."))
        else:
            print(wrap("They’re not biting."))
        if random.random() < 0.1:
            self.handle_incident()

    def action_preserve_meat(self) -> None:
        total_fresh = sum(p.quantity for p in self.player.inventory.fresh_meat)
        if total_fresh <= 0:
            print(wrap("You have no fresh meat to preserve."))
            return
        if self.player.inventory.firewood <= 0 and self.player.inventory.fuel_gallons < 0.2:
            print(wrap("You need firewood or some fuel to keep a steady low fire for hours."))
            return
        print(wrap("You set a smoldering fire and work carefully to turn slices into jerky."))
        self.advance_time(4)
        preserved = 0
        for p in self.player.inventory.fresh_meat:
            convert = min(p.quantity, random.randint(1, p.quantity))
            p.quantity -= convert
            preserved += convert
        self.player.inventory.fresh_meat = [p for p in self.player.inventory.fresh_meat if p.quantity > 0]
        self.player.inventory.jerky += preserved
        # consume some fire resource
        if self.player.inventory.firewood > 0:
            self.player.inventory.firewood = max(0, self.player.inventory.firewood - 1)
        else:
            self.player.inventory.fuel_gallons = max(0.0, self.player.inventory.fuel_gallons - 0.2)
        print(wrap(f"You preserved {preserved} units as jerky."))

    def action_boil_water(self) -> None:
        if self.player.inventory.firewood <= 0 and self.player.inventory.fuel_gallons < 0.1:
            print(wrap("You need some firewood or fuel to boil water safely."))
            return
        print(wrap("You rig a small stove and bring a pot to a steady boil."))
        self.advance_time(2)
        produced = random.randint(1, 3)
        self.player.inventory.water_units += produced
        if self.player.inventory.firewood > 0:
            self.player.inventory.firewood = max(0, self.player.inventory.firewood - 1)
        else:
            self.player.inventory.fuel_gallons = max(0.0, self.player.inventory.fuel_gallons - 0.1)
        print(wrap(f"You made {produced} units of safe water."))

    def action_rest(self) -> None:
        print(wrap("You take time to breathe, hydrate, and let the day settle."))
        self.advance_time(4)
        self.player.stamina = min(100, self.player.stamina + 25)
        self.player.morale = min(100, self.player.morale + 5)

    def action_listen_radio(self) -> None:
        if not self.player.inventory.radio:
            print(wrap("You don’t have a working radio."))
            return
        print(wrap("You tune through static, collecting pieces of a broken day."))
        self.advance_time(1)
        self.random_daily_event()

    def action_travel(self) -> None:
        current = self.current_location_key
        neighbors = self.world.get_neighbors(current)
        print("Where do you want to go?")
        for idx, (dest_key, miles) in enumerate(neighbors, start=1):
            name = self.world.locations[dest_key].name
            print(f"  {idx}) {name} ({miles} mi)")
        choice = prompt(
            "Select destination number (or Enter to cancel): ")
        if not choice.strip():
            print("Travel canceled.")
            return
        try:
            idx = int(choice)
            if idx < 1 or idx > len(neighbors):
                raise ValueError
        except ValueError:
            print("Invalid selection.")
            return
        dest_key, miles = neighbors[idx - 1]
        fuel_needed = miles / 25.0  # assume 25 mpg
        time_needed_hours = max(1, miles // 35)  # rough, accounting for stops
        if self.player.inventory.fuel_gallons >= fuel_needed:
            self.player.inventory.fuel_gallons -= fuel_needed
            print(wrap(f"You drive carefully, conserving fuel. {miles} miles."))
            self.advance_time(int(time_needed_hours))
        else:
            # Walk the remainder
            miles_to_walk = int(miles - self.player.inventory.fuel_gallons * 25.0)
            self.player.inventory.fuel_gallons = 0.0
            walk_hours = max(2, miles_to_walk // 3)
            print(wrap(
                f"Not enough fuel. You walk {miles_to_walk} miles, slow and hot."
            ))
            # walking costs
            self.advance_time(walk_hours)
            self.player.stamina = max(0, self.player.stamina - 30)
            self.player.health = max(0, self.player.health - 5)
        self.current_location_key = dest_key
        print(wrap(f"You arrive in {self.world.locations[dest_key].name}."))
        # travel risks
        if random.random() < 0.2:
            self.handle_incident()

    def handle_incident(self) -> None:
        incidents = [
            ("A shadowed figure keeps pace, then vanishes when you glance back.",
             lambda: self._incident_none()),
            ("You cut your palm on jagged metal.",
             lambda: self._incident_injury()),
            ("A stray dog warns you off a yard you almost crossed. You change course.",
             lambda: self._incident_none()),
            ("Distant voices argue over something small that suddenly matters a lot.",
             lambda: self._incident_morale()),
            ("You step wrong and twist your ankle.",
             lambda: self._incident_ankle()),
        ]
        description, effect = random.choice(incidents)
        print(wrap(description))
        effect()

    def _incident_none(self) -> None:
        # tension without consequence
        pass

    def _incident_injury(self) -> None:
        if self.player.inventory.medkits > 0:
            self.player.inventory.medkits -= 1
            print(wrap("You clean and bandage the wound. It’ll hold."))
        else:
            self.player.health = max(0, self.player.health - 8)
            self.player.morale = max(0, self.player.morale - 5)
            print(wrap("You wrap it with torn cloth. It throbs as you keep moving."))

    def _incident_morale(self) -> None:
        self.player.morale = max(0, self.player.morale - 5)
        print(wrap("The sound follows you for a while."))

    def _incident_ankle(self) -> None:
        self.player.stamina = max(0, self.player.stamina - 25)
        self.player.health = max(0, self.player.health - 5)
        print(wrap("You limp until it loosens. Pain lingers."))

    # ------------- UI -------------
    def show_status(self) -> None:
        loc = self.world.locations[self.current_location_key]
        print()
        print(f"Day {self.day}, {self.hour:02d}:00 | {loc.name} | {self.temperature_f}°F")
        inv = self.player.inventory
        fresh = sum(p.quantity for p in inv.fresh_meat)
        print(
            f"Health {self.player.health}  Stamina {self.player.stamina}  Morale {self.player.morale}\n"
            f"Water {inv.water_units}  Food {inv.food_rations}  Jerky {inv.jerky}  FreshMeat {fresh}\n"
            f"Ammo {inv.ammo_rounds}  Medkits {inv.medkits}  Fuel {inv.fuel_gallons:.1f}  Firewood {inv.firewood}"
        )
        if loc.special == "family_land":
            print("Family property nearby: small pond, potential base.")
        print()

    def show_location_flavor(self) -> None:
        loc = self.world.locations[self.current_location_key]
        print(wrap(loc.description))

    def main_menu(self) -> None:
        print()
        print("What do you do?")
        print("  1) Scavenge")
        print("  2) Hunt")
        print("  3) Fish")
        print("  4) Preserve Meat")
        print("  5) Boil Water")
        print("  6) Rest")
        print("  7) Travel")
        print("  8) Listen to Radio")
        print("  9) Quit")

    def handle_menu_choice(self, choice: str) -> bool:
        if choice == "1":
            self.action_scavenge()
        elif choice == "2":
            self.action_hunt()
        elif choice == "3":
            self.action_fish()
        elif choice == "4":
            self.action_preserve_meat()
        elif choice == "5":
            self.action_boil_water()
        elif choice == "6":
            self.action_rest()
        elif choice == "7":
            self.action_travel()
        elif choice == "8":
            self.action_listen_radio()
        elif choice == "9":
            return False
        else:
            print("Invalid choice.")
        return True

    # ------------- Loop -------------
    def run(self) -> None:
        random.seed(self.random_seed)
        self.show_intro()
        alive = True
        if self.demo_mode:
            # automated short run for non-interactive check
            self.show_status()
            self.show_location_flavor()
            self.action_scavenge()
            self.show_status()
            self.action_hunt()
            self.show_status()
            print(wrap("Demo complete."))
            return
        while alive and self.player.is_alive():
            self.show_status()
            self.show_location_flavor()
            self.main_menu()
            choice = prompt(
                "Choose an action (1-9): ")
            if not self.handle_menu_choice(choice.strip()):
                break
            if not self.player.is_alive():
                alive = False
        if not self.player.is_alive():
            print(wrap("You sit down, dizzy. The world narrows to breath and heat and then it’s just quiet."))
        print(wrap("Thanks for playing."))


def parse_args(argv: List[str]) -> Tuple[bool]:
    demo = False
    for arg in argv[1:]:
        if arg == "--demo":
            demo = True
    return (demo,)


def main() -> None:
    demo_mode, = parse_args(sys.argv)
    game = Game(demo_mode=demo_mode)
    game.run()


if __name__ == "__main__":
    main()