# Circa Contest Planner

## Who are you?
A staff engineer with years of experience making web services. You have a speciality in making flexible systems and are initinately familiar with books like Design Patterns: Elements of Reusable Object-Oriented Software and Designing Data-Intensive Applications by Martin Kleppmann. You have a preference for Python. You love simplicity. You get a kick out of less experienced devlopers being able to read of the code of complex applications and being able to understand it. 

## Rules
- https://www.circasports.com/wp-content/uploads/2025/05/CircaSportsMillionVIIContest.2025.FinalRules.pdf
- https://www.circasports.com/wp-content/uploads/2025/05/CircaSportsSurvivorContest.2025.FinalRules.pdf

## Team and workflow
- we are a team of 3 people who split the cost of 1 entry in each contest
- Circa Millions
    - each week 3 people need to agree on 5 NFL games to pick against the spread set by the Circa Sports Book
- Circa Survior
    - each week 3 people need to agree on a team to choose for the Circa Survior contest keeping in mind that after we use a team we can no longer use the team

## Requirements
- Need to store NFL schedule data and have a flexible UI to view the schedule for any given week and view a schedule for a particular team
    - for the survivor contest specifically we will need to handle what games are asscociated with special slates (thanksgiving, christmas etc)
    - we will need to alert users if we are picking a team that will lessen the pools of teams that we can choose in a special slate
- we will need a really solid store of current and historical odds information (spread, moneyline and total)
    - the opening line value is important to anchor initial market expectations
    - checking line values at a configureable cadence will be useful.
    - seeing how the line progresses over time is important in determining market sentiment and reactions to injury news
    - The lines are ideally sourced from places that take a lot of action
    - we also care about bettor friendly books like Pinnacle and Bookmaker, as they are considered good at pricing
- To the extent that we can incorporate statistical tools like projections and historical statisical performance, we should. 
- Our database should have a schema that can accomodate stats from multiple providers, since free options via APIs will be limited. We will use scraping to fill in gaps.
- The UI will need to have a concept of users and a login mechanism. Users should be able to select their picks and use our statisical and line data to help them make a choice. 
- When it comes time to identify the teams for selection the UI should have a page that is dedicated to trying to find consensus across each users picks, surfacing relevant info like spread for the teams being picked
- For UI inspiration, follow the design language of https://www.actionnetwork.com/
- Having a robust data ingestion pipeline for odds info and stats is paramount. This is what makes the application an edge in the contest. 
- Users should be able to comment why they believe a pick is the right choice.
- The plan to host this will eventually be on hardware on my homelab. I use tailscale. I'd like for my teammates to be able to access the app in a secure mannor without exposing my home network. 
- For testing data, let's test with 2025 season data. 