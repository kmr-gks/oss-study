Introduction
- Introduce Open-source ecosystems (example)
- Some projects are critical to software development around the world, therefore we need to make sure that they continue to be maintained. For this purpose, some projects receive donations via funding platform such as https://opencollective.com/.

Background
What is the difference between previous work and our work?
Main Point: We want to investigate the relationship and the impacts that funding has on a project's software development.

Why?
In theory, open-source projects are maintained by volunteers but if the truth is that they depend on external funding, then it can affect the longevity of the projects and the overall health of the ecosystem that depends on these projects.
Therefore, we aim to:
1. Investigate money contributions made to open-source project (Why are they funding these open-source projects? How much are they giving?)
2. Investigate funding expenditures made by open-source projects that receive external funding (For what purpose are they spending funding? Engineering, Marketing, etc.)
3. Quantitavely measure the impact of receiving external funding on software development activities. (Does funding correlate to higher development activity?)

Methodology
1. Using open-source collective API, we will collect transaction history of open-source projects which includes large amounts of metadata such as:
- Purpose of spending money
- Amount of transaction
- Date
2. Using GitHub contribution history, we will measure the impact of receiving funding on the development activity (e.g., Does spending on engineering directly leads to more active maintenance and development?) 
Contribution History: Pull requests, number of commits, number of active developers during the months preceding the time where the project received funding versus after the project started getting funded

Question: Why do we want to do this kind of analysis? Who is this useful for?
Response: The projects participating to opensource collective are critical open-source infrastructure. If these projects actually rely on donations to be well maintained, it threatens the health of the entire ecosystem --> all companies, organizations, and researchers around the world use and depend on these projects
