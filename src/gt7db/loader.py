from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


def _norm(s: Optional[str]) -> str:
    return " ".join((s or "").strip().lower().split())


@dataclass(frozen=True)
class Car:
    car_id: int
    name: str
    maker_id: str


@dataclass(frozen=True)
class Venue:
    venue_id: int
    name: str
    logo_name: str


@dataclass(frozen=True)
class Layout:
    layout_id: int
    venue_id: int  # "Base" in your CSV
    name: str
    country: str
    category: str
    length: str
    num_corners: str
    is_reverse: str
    is_oval: str


class GT7Database:
    def __init__(
        self,
        cars: Dict[int, Car],
        venues: Dict[int, Venue],
        layouts: Dict[int, Layout],
        cars_by_name: Dict[str, Car],
        layouts_by_name: Dict[str, Layout],
        venues_by_name: Dict[str, Venue],
    ):
        self.cars = cars
        self.venues = venues
        self.layouts = layouts
        self._cars_by_name = cars_by_name
        self._layouts_by_name = layouts_by_name
        self._venues_by_name = venues_by_name

    def find_car_by_id(self, car_id: int) -> Optional[Car]:
        return self.cars.get(car_id)

    def find_layout_by_id(self, layout_id: int) -> Optional[Layout]:
        return self.layouts.get(layout_id)

    def find_venue_by_id(self, venue_id: int) -> Optional[Venue]:
        return self.venues.get(venue_id)

    def best_match_car(self, name: str) -> Optional[Car]:
        return self._cars_by_name.get(_norm(name))

    def best_match_layout(self, name: str) -> Optional[Layout]:
        return self._layouts_by_name.get(_norm(name))

    def best_match_venue(self, name: str) -> Optional[Venue]:
        return self._venues_by_name.get(_norm(name))

    @classmethod
    def load(cls, db_root: Path) -> "GT7Database":
        cars_path = db_root / "gt7_car.csv"
        venues_path = db_root / "gt7_venues.csv"
        layouts_path = db_root / "gt7_layouts.csv"

        cars: Dict[int, Car] = {}
        venues: Dict[int, Venue] = {}
        layouts: Dict[int, Layout] = {}

        cars_by_name: Dict[str, Car] = {}
        venues_by_name: Dict[str, Venue] = {}
        layouts_by_name: Dict[str, Layout] = {}

        # Cars (Model,...,CarID,MakerID)
        with cars_path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                car = Car(
                    car_id=int(row["CarID"].strip()),
                    name=row["Model"].strip(),
                    maker_id=(row.get("MakerID") or "").strip(),
                )
                cars[car.car_id] = car
                cars_by_name[_norm(car.name)] = car

        # Venues (VenueID,VenueName,LogoName)
        with venues_path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                venue = Venue(
                    venue_id=int(row["VenueID"].strip()),
                    name=row["VenueName"].strip(),
                    logo_name=(row.get("LogoName") or "").strip(),
                )
                venues[venue.venue_id] = venue
                venues_by_name[_norm(venue.name)] = venue

        # Layouts (LayoutID,LayoutName,Base,...,NumCorners,...)
        with layouts_path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                layout = Layout(
                    layout_id=int(row["LayoutID"].strip()),
                    venue_id=int(row["Base"].strip()),
                    name=row["LayoutName"].strip(),
                    country=(row.get("Country") or "").strip(),
                    category=(row.get("Category") or "").strip(),
                    length=(row.get("Length") or "").strip(),
                    num_corners=(row.get("NumCorners") or "").strip(),
                    is_reverse=(row.get("IsReverse") or "").strip(),
                    is_oval=(row.get("IsOval") or "").strip(),
                )
                layouts[layout.layout_id] = layout
                layouts_by_name[_norm(layout.name)] = layout

        return cls(
            cars=cars,
            venues=venues,
            layouts=layouts,
            cars_by_name=cars_by_name,
            venues_by_name=venues_by_name,
            layouts_by_name=layouts_by_name,
        )
