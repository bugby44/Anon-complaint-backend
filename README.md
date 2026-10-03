# Anonymous Complaint API

A backend for an anonymous complaint box. You file a complaint without making an account and get back a random code. That code is how you check on it later. Moderators log in with a password to see all complaints and update their status.

Built with FastAPI, SQLAlchemy and Postgres. Hosted on Render.

## Live demo

https://whistle-drop-api.onrender.com/

The link redirects to the Swagger docs, where you can try every endpoint from the browser.

Note: the free Render tier sleeps when idle, so the first request can take 30 to 50 seconds. After that it is fast.

<!-- SCREENSHOT 1: /docs overview -->
<img src="screenshots/Screenshot main page.png" width="750">

## How it works

The complainant clicks on try it out to begin and type the category, description and an optional url as proof. This data is then stored on Postgres and a random 16-character hex code is returned. That code is how the complainant can check on the status of their complaint later.

Status is set to SUBMITTED by default and a moderator, using the password can change the status after reviewing the complaint.The complainant can check the status at any time using the unique code of the complaint.

The moderator can also filter the complaints by category and status.

Nothing identifying is stored. No name, no email, no IP address.

## Endpoints

POST /complaints submits a complaint and returns your code.

GET /complaints/{code} gives you the category and current status.

GET /mod/complaints lists everything and requires the moderator password to access. You can filter with ?category= and ?status=.

PATCH /mod/complaints/{code} changes a complaint's status. Also needs the password.

The moderator password goes in an X-Mod-Password header. In Swagger there is a field for it on those two endpoints.

Categories are Security, Harassment, Corruption, Technical and Other. Statuses are SUBMITTED, UNDER REVIEW and RESOLVED. Anything else gets rejected with a 422 error code.

Pydantic checks every request before it reaches the database. The category and status have to be one of the allowed values, the proof link has to be a valid http or https URL, and the description cannot be empty. If anything is wrong the request gets rejected with a 422 and a message naming the field.

The submit form has no status or code field at all, so a complainant cannot set their own status or choose their own code. The moderator's update only has a status field, so they cannot edit the text of a complaint.

## Submitting a complaint
Input:
<!-- SCREENSHOT 2: POST /complaints request body -->
<img src="screenshots/Screenshot Create Complaint input.png" width="750">

Output:
<!-- SCREENSHOT 3: POST /complaints response with the hex code -->
<img src="screenshots/Screenshot Create Complaint output.png" width="750">

## Checking the status of a complaint
Input:
<!-- SCREENSHOT 4: GET /complaints/{code} -->
<img src="screenshots/Screenshot Get Status input.png" width="750">

Output:
<!-- SCREENSHOT 5: GET /complaints/{code} -->
<img src="screenshots/Screenshot Get Status Output.png" width="750">

## Moderator getting complaint data and filtering by category
Input:
<!-- SCREENSHOT 6: GET /mod/complaints -->
<img src="screenshots/Screenshot Get Data mod input.png" width="750">

Output:
<!-- SCREENSHOT 7: GET /mod/complaints -->
<img src="screenshots/Screenshot Get data mod output.png" width="750">


## Moderator updating status of a complaint
Input:
<!-- SCREENSHOT 8: PATCH changing the status -->
<img src="screenshots/Screenshot Update status input.png" width="750">

Output:
<!-- SCREENSHOT 9: PATCH changing the status -->
<img src="screenshots/Screenshot Update status output.png" width="750">

## Error
Invalid password returns a 401 error code and a message. 
<!-- SCREENSHOT 10: Error message for wrong password -->
<img src="screenshots/Screenshot Wrong Password.png" width="750">

## In the database

<!-- SCREENSHOT 11: Neon SQL editor showing the rows -->
<img src="screenshots/Screenshot Database.png" width="750">

## Testing it

The moderator password for the demo is 123454321. It is only for testing. The real one is set as an environment variable and is not in this repo.

Try submitting a complaint, copying the code, checking its status, then using the moderator endpoints to find it and set it to RESOLVED. Check the status again and you will see it changed.

## Running it locally

```bash
git clone https://github.com/bugby44/Anon-complaint-backend.git
cd Anon-complaint-backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Make a `.env` file with:

```
MOD_PASSWORD=123454321
```

If you do not set DATABASE_URL it uses a local SQLite file, so there is nothing else to configure. To use Postgres instead, add:

```
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
```

Then run:

```bash
uvicorn main:app --reload
```

and open http://127.0.0.1:8000/docs

## Built with

FastAPI, SQLAlchemy 2.1, Pydantic v2, Postgres on Neon, SQLite locally, hosted on Render.
