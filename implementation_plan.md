# Implementation Plan: Semantic Keyword Maps (Todo Item #3)

This plan outlines the steps to implement the "semantic keyword maps from the concept of the site" feature.

## Overview

The goal is to allow users to define a "concept" for their store, generate a semantic keyword map based on that concept using an LLM, store this map, and allow users to view and edit both the concept and the map within the store settings UI. Generation will prompt the user for confirmation before overwriting existing manual edits to the map.

## Detailed Steps

1.  **Database Migration:**
    *   Modify `models.py`: Add `concept = db.Column(db.Text, nullable=True)` and `keyword_map = db.Column(JSON, nullable=True)` to the `Store` class.
    *   Generate and apply a database migration using Flask-Migrate/Alembic (e.g., `flask db migrate -m "Add concept and keyword_map to Store"` and `flask db upgrade`).

2.  **AI Service:**
    *   Create a function `generate_keyword_map(concept: str) -> dict` (e.g., in `ai_services/claude.py` or a new `ai_services/seo_service.py`).
    *   This function will:
        *   Take the store concept text as input.
        *   Construct an appropriate prompt for the configured LLM (e.g., Claude) asking for a semantic keyword map (e.g., related keywords, possibly categorized).
        *   Call the LLM API.
        *   Parse the response and return it as a Python dictionary representing the keyword map. Handle potential LLM errors.

3.  **Backend (Flask Routes):**
    *   **Store Settings Update:**
        *   Locate the existing route that handles saving store settings (likely in `store_management.py` or `app.py`, handling `POST` requests for the store form).
        *   Modify this route to retrieve `concept` and `keyword_map` from the submitted form data.
        *   Parse the `keyword_map` string from the form into a Python dictionary/JSON before saving to the database. Handle potential JSON parsing errors.
        *   Save the updated `store.concept` and `store.keyword_map` to the database.
    *   **Keyword Map Generation:**
        *   Create a new route: `POST /stores/<int:store_id>/generate_keyword_map`.
        *   This route should:
            *   Fetch the `Store` object by `store_id`.
            *   Get the `store.concept`. If the concept is empty or null, return a JSON error response (e.g., `{'error': 'Store concept is not defined.'}`, status 400).
            *   Call the `generate_keyword_map(store.concept)` function from the AI service.
            *   If the AI service returns a map successfully, return it as a JSON response (e.g., `jsonify(keyword_map)`).
            *   If the AI service raises an error, return a JSON error response (e.g., `{'error': 'Failed to generate keyword map.'}`, status 500).
            *   **Note:** This route *only returns* the generated map; it does not save it directly.

4.  **Frontend (Templates/JS):**
    *   Modify the store settings template (likely `templates/store_form.html`):
        *   Inside the `<form>` for editing the store:
            *   Add a label and `<textarea name="concept" class="form-control">` field, populating its content with `{{ store.concept or '' }}`.
            *   Add a label and `<textarea name="keyword_map" class="form-control" rows="10">` field. Populate its content with the pretty-printed JSON of the keyword map (e.g., using a Jinja filter or passing it pre-formatted from the backend: `{{ store_keyword_map_json or '{}' }}`).
            *   Add a button: `<button type="button" id="generate-keyword-map-btn" class="btn btn-secondary mt-2">Generate Keyword Map</button>`.
    *   Add JavaScript (either inline in the template or in a linked `.js` file):
        *   Get references to the concept textarea, keyword map textarea, and the generate button.
        *   Add a `click` event listener to the `generate-keyword-map-btn`.
        *   Inside the listener:
            *   Get the current value from the `keyword_map` textarea (`keywordMapTextarea.value`).
            *   Check if the map textarea is effectively empty (e.g., `!keywordMapTextarea.value.trim() || keywordMapTextarea.value.trim() === '{}' || keywordMapTextarea.value.trim() === 'null'`).
            *   `let proceed = isMapEmpty;`
            *   `if (!isMapEmpty) { proceed = window.confirm("Generating a new keyword map will overwrite your current edits. Proceed?"); }`
            *   `if (proceed)`:
                *   Disable the generate button temporarily.
                *   Make an asynchronous `fetch` request (`POST`) to the `/stores/<store_id>/generate_keyword_map` endpoint (ensure `<store_id>` is available in the JS context). Include necessary headers (`Content-Type: application/json`, CSRF token if applicable).
                *   Handle the response:
                    *   If `response.ok`: Parse the JSON body (`response.json()`). Pretty-print the resulting map object (`JSON.stringify(data, null, 2)`) and set it as the value of the `keyword_map` textarea.
                    *   If `!response.ok`: Parse error JSON if available (`response.json()`) and display an alert to the user (e.g., `alert('Error: ' + (errorData.error || 'Failed to generate map'))`).
                *   Handle fetch errors (e.g., network issues).
                *   Re-enable the generate button.
    *   Ensure the main `<form>` submission correctly sends the `concept` and `keyword_map` textarea contents to the backend update route.

## Workflow Diagram

```mermaid
graph TD
    A[DB Migration] --> B[AI Service];
    B --> C[Backend Routes];
    C --> D[Frontend UI];
    D --> E{User Flow};

    subgraph A [DB Migration]
        A1[Add concept field to Store model];
        A2[Add keyword_map (JSON) field to Store model];
        A3[Generate & Apply Migration];
    end

    subgraph B [AI Service]
        B1[Function: generate_keyword_map(concept)];
        B2[Input: Store Concept Text];
        B3[Process: Call LLM (Claude)];
        B4[Output: Keyword Map (dict)];
    end

    subgraph C [Backend Routes]
        C1[Update Store Settings Route (Save concept/map)];
        C2[New Route: POST /generate_keyword_map (Returns generated map)];
    end

    subgraph D [Frontend UI (Store Settings)]
        D1[Textarea for Concept];
        D2[Textarea for Keyword Map (Editable JSON)];
        D3[Button: "Generate Keyword Map"];
        D4[JavaScript: AJAX call to generate];
        D5[JS Logic: Check if map textarea is empty];
        D6[JS Logic: If not empty, confirm overwrite with user];
        D7[JS Logic: If confirmed or was empty, update textarea with result];
        D8[Form Submit: Saves both textareas];
    end

    subgraph E [User Flow]
        E1[User edits Concept];
        E2[User clicks Generate];
        E3[JS checks if map exists];
        E4[If exists, JS asks user to confirm overwrite];
        E5[If confirmed or was empty, JS calls backend, updates map textarea];
        E6[User manually edits Keyword Map textarea];
        E7[User saves Store Settings];
    end

    A --> A1 & A2 --> A3;
    B --> B1 & B2 & B3 & B4;
    C --> C1 & C2;
    D --> D1 & D2 & D3 & D4 & D5 & D6 & D7 & D8;
    E --> E1 & E2 --> E3 --> E4 --> E5 & E6 --> E7;

    A3 --> C1;
    B1 --> C2;
    C2 --> D4; % Backend route called by JS
    D4 --> D7; % JS updates textarea on success
    D8 --> E7; % Form submit triggers save
    D3 --> E2; % Button click starts flow
    D2 --> E6; % User edits textarea
    D5 --> E3; % JS check
    D6 --> E4; % JS confirm
```

## Next Steps

Proceed with implementation by switching to 'code' mode.