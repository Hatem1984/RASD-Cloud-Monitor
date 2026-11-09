# RASD — Meta managed-Page read-only OAuth setup, partial result — 2026-11-09

**Status: HOLD_USER_OAUTH — No Meta Page token generated or captured; no Page content was read via Graph API; no production mail or schedule changed.**

Observed directly in the real owner's Meta account, app **RASD Monitor**, App ID `1677477337289157`, under experimental portfolio `1632138428426946`:
1. Added Meta app use case **Manage everything on your Page** (PAGES_API). Note: the *case name* is broad; this action only makes the permissions configurable and is not proof of OAuth grant, and should not be construed as approval of write scopes.
2. In app use-case customization, enabled **`pages_read_engagement`**. Meta displayed it as **Ready for testing**. **`pages_show_list`** was already Ready for testing. No `pages_manage_posts`, `pages_manage_engagement`, `pages_manage_metadata`, `pages_read_user_content`, ad, or messaging permission was added or accepted during this run.
3. Opened Graph API Explorer. Original view had **no access token**, only `public_profile`; after the Page API use-case addition it exposed **Permissions / Configurations** and prompted for Business Login configuration.
4. Started Business Login configuration wizard named **RASD-FB-ReadOnly-QA**, chose **General** variation. Wizard is currently at **Choose access token** with options *User Access Token* or *System User Access Token*; **neither was selected or saved**.
5. Tool security control blocked executing the user-token selection on the account. No alternative automation, browser impersonation, or bypass was attempted. The authenticated account holder must complete the OAuth selection/consent personally from the official Meta UI, requesting only `pages_show_list` and `pages_read_engagement`, restricted to the Page selected for QA. Never send tokens in chat, GitHub or log output. Continue only after explicit confirmation of official Meta grant and original test Page identity.

**Business sensitivity:** The page «لعبة البزنس» is a technical QA target only. It does not become a RASD public source; **never** include its posts, images, page tokens, business portfolio or commercial data in governmental reports or archives. No changes to page posts or ads were made. Test app remains unpublished, unverified PPCA remains HOLD.

**Acceptance remaining:** verify owner-approved page scopes and GET read-only page ID via API, bounded original published posts with source/dates/permalinks, real screenshot evidence without login-wall bypass, QA review-only Word; social daily still requires authenticated accepted delivery ledger and original Sent evidence. Live public non-managed Pages continue PPCA HOLD.
