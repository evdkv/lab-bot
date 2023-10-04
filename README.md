Lab Schedule Slack Bot
=======================
This is the backend code for a Slack app to help
lab members manage their testing schedules. Right now,
it can access a Firestore database, validate workspace users, and
pull a schedule summary for each user.<br>

Features
========================

Adding Slots to the Calendar
----------------------------

The form can be acccessed through /add-slot command, then it prompts the user 
to enter the information for their new time slot

![add slot](/img/add-slot.gif)

Then, the request goes to the selected approver and they get a request and have
an option to either approve it or reject it.

![approve](/img/approve.gif)

If approved, the event is added to the database and will appear on the lab calendar.

![approve](/img/cal.gif)

*Project in progress*