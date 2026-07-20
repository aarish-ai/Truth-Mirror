# Beta Launch Plan

1. **Verify Frontend Stability**
   * Check for JavaScript console errors on a fresh result.
   * Open DevTools in the browser and submit a claim. Ensure there are zero JS errors in the console. Pay special attention to potential null references resulting from edge-case result shapes, particularly given the recent source table refactor.

2. **Evaluate User Runtime Expectations**
   * Review the 2 to 5 minute pipeline wait time.
   * Sit through the full wait yourself on a fresh claim and honestly assess: would a first-time user think the application is broken before the result appears?
   * If the answer is maybe, consider whether the fun loading messages cycle fast enough to make the application feel alive.

3. **Assess API Capacity**
   * Calculate how many claims per day the application can handle.
   * Determine the ceiling based on your current free tier API limits across Groq and Gemini.
   * Ensure that expected beta usage (e.g., 20 users submitting 3 claims a day) will not exhaust the quota. Running out of quota mid-beta without a graceful error message would create a bad first impression.

4. **Set Up Hosting**
   * Move the application off localhost so it is accessible to beta users.
   * Set up a simple VPS with Python and the `.env` file. This is the critical step to transition from "it works on my machine" to "people can try it."

5. **Implement Access Control**
   * Add authentication to protect the application on a public URL and prevent unauthorized users from hammering your API keys.
   * For a small private beta, implement at least a shared password, a whitelist of users, or simple HTTP basic auth.
