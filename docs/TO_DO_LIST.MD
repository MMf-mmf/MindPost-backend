

# TODO LIST
- [ ] Mobile issues
  - [] add a delete account endpoint and finish it on the front end so it logs out the user `await apiClient.delete('/api/account/delete/');`
  - [] deleting images on saved posts not working
  - [] posting images to x not working (this is working on the web so its a code issue in the api view)
  - [] if unable to post with image don't post at all and have the user remove the image or properly authenticate with x 1.0
-[🛠️] added initial working versions of auth 1.0 workflow for image upload testing still needed (this is only for the web the app/api needs to be further configured that the correct files are passed to the create post functions...)
- [] if the users has auth 1.0 creds us it and do not let users upload images unless they have auth 1.0 creds
- [ ] get the app online/the app store Apple

- [ ] Migrate api to use FastAPI and take advantage of the async features and its built in background task system

- 14. [ ] set up background tasks when uploading a audio file that will do the transcription and embedding to slim down request time 
- 15. [ ] once 14 is done update the UI to pull every second that the transcription is not there up to 10 time/seconds
- [ ] make the endpoint async
- [ ] touch up all pages so that they the text and all the elements are larger on mobile devices

- [ ] get the application working on android devices
  - [ ] icons do not display
  - [ ] keyboard is covering text input
  - [ ] some buttons such as edit buttons on post page not working
- [ ] deploy to the google play store

- [ ] add the ability to upload pictures to the posts

- [ ] update the chat to be able to have stateful conversations
- [ ] create a middleware to refresh the users tokens when ever they use the app so they do not lose access to there account

- [ ] Allow users to select post from other accounts to mimic the that style of posting (then we will scrap that feed with our api or other ways to get the posts)
- [ ] Holding add a char count count to the select multiple dumps list page 


# BEFORE DEPLOYMENT
- 16. [ ] Once the app is live! NOTE href="vscode://file/ AS AN EXAMPLE WILL OPEN VSCODE SO WE NEED TO GET THE CORRECT URL FOR THE APP ON A USERS DEVISE TO OPEN IT 
- 17. [ ] if more then 166 users subscribe we will need to put them on a waiting list and tell them we will notify them in the next 48 hours when we increase the capacity / increase the X API tier


#  TWITTER CONSTRAINTS TO LOOK INTO
Basic ($2000) POST TWEET LIMIT

PER APP	100 requests / 24 hours
PER USER
1667 requests / 24 hours
which will allow us to give 10 posts per day to to to 166 users per app we can create 2 apps to get 333 users 
Note: that if we go passed 166 users we will need to come up with a way to authenticate some users with one app and some users with another app.

Pro ($5000) POST TWEET LIMIT
100 requests / 15 mins
PER USER
10000 requests / 24 hours
which will allow us to give 10 posts per day to to to 1000 users


# IDEAS
- [ ] when the user clicks to generate a post (experiment) that perhaps if we preprocess the different BrainDumps to see which ones are connected/similar and then group them together
# COMING SOON
- [ ] add linkedIn to the social media connections 
- [ ] add a drop down when creating the posts to select the social media platform the post should be tailored to 

# COMPLETED TASKS
 [✅] make the create post from dump detail more pronounced and when the users clicks on it it should have a animation where it says "Generating post" with ... and the elipses should be animated and then when the posts are returned the page should animate to the post options page
 [✅] on the posts list should not have a create new posts button.
[✅] the post list items should be clickable and should take us to a post detail page the with the same functionality as the post detail page on the web (we should be able to edit the post if it has not already been published, delete it, and publish it, and view the post details as well as a link back to the original BrainDump)

 [✅] create a basic function to retrieve similar BrainDumps
[✅] create a linking system that is a way for the BrainDumps to be related (this was done with hashtags and embeddings)
 [✅] allow the user to select all or some of the recordings and generate a Post from it
[✅] allow the user to edit the transcript and save it

[✅] the post will be generated and will be editable as well in a text editor (where the user can touch it up and then save it to draft or publish it)
[✅] create a model to save posts (draft/published)
[✅] the user can save a post to draft or publish it 
[✅] create a list view and of posts like smiler to the brain dumps list view (paginated, grouped by date) and allow the user to view/publish/edit/delete them
- [✅] create a basic rag chat to allow the user to ask questions like remind me about the guy i met in greece
- [✅] if the post was already published i can not be published again unless it was edited after it was last published ect.
- [✅] implement a proper settings page to allow users to manage all there social connections (twitter, facebook, linkedin ect.) and when a user is not logged in they will reconnect from there. ( remove connect button from the list pages)
- [✅] revamp the sign up process to allow the user to select the tier they want to sign up with 
   - [✅] paid tier $15 for basic
   - [✅] pro tier $30 for pro
- [✅] add a basic stripe payment system to allow users to pay the monthly fee
- [✅] create a robust rate limiting system which will block the users from recording/posting/chatting if they pass there limit or if they simply don't have a active subscription
- [✅] return the char_limit based on what we know about the users subscription tier which might not be accurate but we can display a warning to the user if they are over the limit.
- [✅] allow the users to suggest the ai a char limit for the post
- [✅] update the users char_limit ans subscription status when ever the user authenticates or token is refreshed
- [✅] add all the .env and creds.json with the gcloude secrets
- [✅] link domain to working production instance 
- [✅] touch up the post generation so that there are different templates prompts we pass to the AI based on the length of the input text and char limit specified
- [✅] added encryption and decryption for access token storage
- [✅] make sure that the access tokens are indeed encrypted by viewing the data in the db
- [✅] also encrypt the users transcription
- [½] add more security to our login system to protect against brute force attacks (added somting for the api and added rate limiting to the cloude flare)