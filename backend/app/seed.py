"""Seed the database with NFL teams."""
from app.database import SessionLocal, engine, Base
from app.models import Team

NFL_TEAMS = [
    ("ARI", "Arizona Cardinals", "NFC", "West"),
    ("ATL", "Atlanta Falcons", "NFC", "South"),
    ("BAL", "Baltimore Ravens", "AFC", "North"),
    ("BUF", "Buffalo Bills", "AFC", "East"),
    ("CAR", "Carolina Panthers", "NFC", "South"),
    ("CHI", "Chicago Bears", "NFC", "North"),
    ("CIN", "Cincinnati Bengals", "AFC", "North"),
    ("CLE", "Cleveland Browns", "AFC", "North"),
    ("DAL", "Dallas Cowboys", "NFC", "East"),
    ("DEN", "Denver Broncos", "AFC", "West"),
    ("DET", "Detroit Lions", "NFC", "North"),
    ("GB", "Green Bay Packers", "NFC", "North"),
    ("HOU", "Houston Texans", "AFC", "South"),
    ("IND", "Indianapolis Colts", "AFC", "South"),
    ("JAX", "Jacksonville Jaguars", "AFC", "South"),
    ("KC", "Kansas City Chiefs", "AFC", "West"),
    ("LAC", "Los Angeles Chargers", "AFC", "West"),
    ("LAR", "Los Angeles Rams", "NFC", "West"),
    ("LV", "Las Vegas Raiders", "AFC", "West"),
    ("MIA", "Miami Dolphins", "AFC", "East"),
    ("MIN", "Minnesota Vikings", "NFC", "North"),
    ("NE", "New England Patriots", "AFC", "East"),
    ("NO", "New Orleans Saints", "NFC", "South"),
    ("NYG", "New York Giants", "NFC", "East"),
    ("NYJ", "New York Jets", "AFC", "East"),
    ("PHI", "Philadelphia Eagles", "NFC", "East"),
    ("PIT", "Pittsburgh Steelers", "AFC", "North"),
    ("SEA", "Seattle Seahawks", "NFC", "West"),
    ("SF", "San Francisco 49ers", "NFC", "West"),
    ("TB", "Tampa Bay Buccaneers", "NFC", "South"),
    ("TEN", "Tennessee Titans", "AFC", "South"),
    ("WAS", "Washington Commanders", "NFC", "East"),
]


def seed_teams():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Team).count() > 0:
            print("Teams already seeded.")
            return
        for abbr, name, conf, div in NFL_TEAMS:
            db.add(Team(abbreviation=abbr, name=name, conference=conf, division=div))
        db.commit()
        print(f"Seeded {len(NFL_TEAMS)} NFL teams.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_teams()
