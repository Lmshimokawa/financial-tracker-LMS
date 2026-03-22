# Telegram Message Batching

## 1. Problem Description

The Telegram Bot API enforces a hard limit of **4096 characters** per message. The Financial Tracker n8n workflow sends responses to Telegram using HTML `parse_mode`, and several nodes can produce messages that exceed this limit:

| Node | Risk Level | Reason |
|------|-----------|--------|
| `Reply user - query result` | **High** | Lists multiple transactions; a query returning 20+ items easily exceeds 4096 chars |
| `Send Weekly Summary` | **High** | Aggregates an entire week of data with multiple sections |
| `Send Monthly Summary` | **High** | Aggregates an entire month of data with multiple sections |
| `Format Parcelas Response` | **Medium** | Lists installment details that can grow with many parcelas |

When a message exceeds 4096 characters, the Telegram API returns an error and the user receives **nothing** -- a silent failure from the user's perspective.

### Current Behavior

All Telegram send nodes (`Reply user - query result`, `Send Weekly Summary`, `Send Monthly Summary`, etc.) send a **single message** with the full content using `parse_mode: HTML`. There is no splitting, truncation, or overflow handling.

---

## 2. Solution: Reusable Telegram Message Batcher

Create a **Code node** in n8n that can be placed before any Telegram send node. It takes the full message text, splits it into chunks that respect the Telegram limit, and outputs an array of message parts that are then sent sequentially.

### Design Principles

- **Max chunk size: 4000 characters** (leaves a 96-char buffer for safety and pagination indicators)
- **Smart splitting**: splits at logical boundaries -- section separators (`━━━━━━━━━`), double newlines, single newlines -- before falling back to character-level splitting
- **HTML-safe**: tracks open HTML tags and re-opens them in the next chunk so formatting is never broken
- **Pagination**: appends `(1/3)`, `(2/3)`, `(3/3)` when a message is split into multiple parts
- **Pass-through for short messages**: messages under the limit are returned as-is (single-element array)

---

## 3. Complete Batcher Code (n8n Code Node - JavaScript)

```javascript
// ============================================================
// Telegram Message Batcher - n8n Code Node
// ============================================================
// Input:  $input.all() — expects item(s) with json.message (string)
//         Also passes through json.chatId for routing.
// Output: Array of items, each with json.messageChunk and json.chatId
// ============================================================

const MAX_CHUNK_SIZE = 4000; // 4096 limit minus buffer for pagination + safety

// Section separator patterns used in the Financial Tracker
const SECTION_SEPARATORS = [
  '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
  '━━━━━━━━━━━━━━━━━━━━',
  '━━━━━━━━━━',
  '──────────',
  '═══════════',
];

/**
 * Find all open HTML tags that haven't been closed in a text fragment.
 * Returns an array of tag names in order of opening.
 */
function getUnclosedTags(text) {
  const openTags = [];
  // Match opening and closing HTML tags
  const tagRegex = /<\/?([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>/g;
  let match;

  while ((match = tagRegex.exec(text)) !== null) {
    const fullMatch = match[0];
    const tagName = match[1].toLowerCase();

    // Self-closing tags to ignore
    if (fullMatch.endsWith('/>')) continue;
    // Void elements that don't need closing
    if (['br', 'hr', 'img', 'input'].includes(tagName)) continue;

    if (fullMatch.startsWith('</')) {
      // Closing tag — remove the last matching open tag
      const idx = openTags.lastIndexOf(tagName);
      if (idx !== -1) {
        openTags.splice(idx, 1);
      }
    } else {
      // Opening tag
      openTags.push(tagName);
    }
  }

  return openTags;
}

/**
 * Generate closing tags for a list of open tag names (in reverse order).
 */
function buildClosingTags(tags) {
  return tags.slice().reverse().map(t => `</${t}>`).join('');
}

/**
 * Generate opening tags to re-open previously unclosed tags.
 * Note: attributes are NOT preserved (Telegram supports limited HTML:
 * <b>, <i>, <u>, <s>, <code>, <pre>, <a href="...">).
 * For <a> tags we cannot reliably reconstruct the href, so we skip re-opening them.
 */
function buildReopeningTags(tags) {
  return tags.filter(t => t !== 'a').map(t => `<${t}>`).join('');
}

/**
 * Find the best split point in text before maxPos.
 * Priority: section separator > double newline > single newline > last space.
 */
function findSplitPoint(text, maxPos) {
  const searchZone = text.substring(0, maxPos);

  // 1. Try splitting at a section separator line
  for (const sep of SECTION_SEPARATORS) {
    const idx = searchZone.lastIndexOf(sep);
    if (idx > 0) {
      // Find the start of the line containing the separator
      const lineStart = searchZone.lastIndexOf('\n', idx - 1);
      if (lineStart > 0) {
        return lineStart;
      }
      return idx;
    }
  }

  // 2. Try splitting at a double newline (paragraph break)
  const doubleNewline = searchZone.lastIndexOf('\n\n');
  if (doubleNewline > 0) {
    return doubleNewline;
  }

  // 3. Try splitting at a single newline
  const singleNewline = searchZone.lastIndexOf('\n');
  if (singleNewline > 0) {
    return singleNewline;
  }

  // 4. Try splitting at a space
  const lastSpace = searchZone.lastIndexOf(' ');
  if (lastSpace > 0) {
    return lastSpace;
  }

  // 5. Hard split at maxPos (last resort)
  return maxPos;
}

/**
 * Split a message into Telegram-safe chunks.
 */
function batchMessage(message) {
  if (!message || message.length === 0) {
    return [''];
  }

  // If message fits in a single chunk, return as-is
  if (message.length <= MAX_CHUNK_SIZE) {
    return [message];
  }

  const chunks = [];
  let remaining = message;

  while (remaining.length > 0) {
    if (remaining.length <= MAX_CHUNK_SIZE) {
      chunks.push(remaining);
      break;
    }

    // Account for closing tags that may need to be appended
    const unclosed = getUnclosedTags(remaining.substring(0, MAX_CHUNK_SIZE));
    const closingTagsLength = buildClosingTags(unclosed).length;
    const effectiveMax = MAX_CHUNK_SIZE - closingTagsLength - 20; // 20 chars for pagination

    const splitAt = findSplitPoint(remaining, effectiveMax);

    let chunk = remaining.substring(0, splitAt);

    // Close any open HTML tags at the end of this chunk
    const openTags = getUnclosedTags(chunk);
    if (openTags.length > 0) {
      chunk += buildClosingTags(openTags);
    }

    chunks.push(chunk);

    // Start next chunk: skip whitespace/newlines at the split, then re-open tags
    let nextStart = splitAt;
    while (nextStart < remaining.length &&
           (remaining[nextStart] === '\n' || remaining[nextStart] === '\r')) {
      nextStart++;
    }

    let nextPrefix = '';
    if (openTags.length > 0) {
      nextPrefix = buildReopeningTags(openTags);
    }

    remaining = nextPrefix + remaining.substring(nextStart);
  }

  // Add pagination indicators if we have multiple chunks
  if (chunks.length > 1) {
    const total = chunks.length;
    for (let i = 0; i < chunks.length; i++) {
      chunks[i] = chunks[i].trimEnd() + `\n\n<i>(${i + 1}/${total})</i>`;
    }
  }

  return chunks;
}

// ---- Main execution ----
const results = [];

for (const item of $input.all()) {
  const message = item.json.message || item.json.text || '';
  const chatId = item.json.chatId || item.json.chat_id || '';

  const chunks = batchMessage(message);

  for (const chunk of chunks) {
    results.push({
      json: {
        messageChunk: chunk,
        chatId: chatId,
        // Pass through any other fields that downstream nodes may need
        ...(item.json.reply_to_message_id && { reply_to_message_id: item.json.reply_to_message_id }),
      }
    });
  }
}

return results;
```

---

## 4. Wrapper Approach: Integration Strategies

There are two ways to integrate the batcher into the workflow.

### Option A: Inline Code Node Before Each Telegram Send (Recommended for few nodes)

Insert the Code node directly before each high-risk Telegram send node.

```
[Existing logic] → [Message Batcher (Code)] → [Telegram Send Message]
                                                 ↑ uses {{ $json.messageChunk }}
```

**Steps per node:**

1. Add a new **Code node** named e.g. `Batch - Query Result`
2. Paste the batcher code above
3. Connect the output of the existing formatting node to this new Code node
4. Connect the Code node output to the existing Telegram send node
5. In the Telegram send node, change the **Text** field from the original expression to:
   ```
   {{ $json.messageChunk }}
   ```
6. Ensure the **Chat ID** field uses:
   ```
   {{ $json.chatId }}
   ```

The Code node outputs multiple items when batching occurs. The n8n Telegram node will execute **once per item**, so each chunk is sent as a separate message automatically.

### Option B: Sub-Workflow (Recommended for many nodes)

Create a reusable sub-workflow that encapsulates both the batching logic and the Telegram send action.

**Sub-workflow: "Send Telegram Batched"**

```
[Start / Trigger] → [Message Batcher (Code)] → [Telegram Send Message]
```

The sub-workflow accepts parameters:
- `message` (string) -- the full message text
- `chatId` (string) -- the Telegram chat ID
- `reply_to_message_id` (string, optional) -- for reply threading

**In the main workflow**, replace each Telegram send node with an **Execute Sub-Workflow** node:

```
[Existing logic] → [Execute Sub-Workflow: "Send Telegram Batched"]
                     ↑ passes message, chatId
```

**Advantages of the sub-workflow approach:**
- Single place to update the batching logic
- Main workflow stays clean
- Can add rate limiting (Telegram allows ~30 msgs/sec) in one place
- Can add error handling / retry logic once

---

## 5. Implementation Instructions for n8n

### Step-by-Step: Option A (Inline)

Target these four nodes first, as they have the highest overflow risk:

#### 5.1 Patch "Reply user - query result"

1. Open the workflow in the n8n editor
2. Locate the node that feeds into `Reply user - query result` (the formatting/code node that builds the query result message)
3. **Add a Code node** between the formatting node and `Reply user - query result`:
   - Name: `Batch Query Result`
   - Language: JavaScript
   - Paste the full batcher code from Section 3
4. Ensure the upstream node outputs `{ message: "<the full HTML text>", chatId: "<chat_id>" }`
   - If the upstream node uses a different field name (e.g., `text`), the batcher handles both `message` and `text`
5. Rewire: `[Format node] → [Batch Query Result] → [Reply user - query result]`
6. In `Reply user - query result`, update the **Text** field to: `{{ $json.messageChunk }}`

#### 5.2 Patch "Send Weekly Summary"

1. Add a Code node `Batch Weekly Summary` before `Send Weekly Summary`
2. Paste the batcher code
3. Rewire the connections
4. Update the Text field in the Telegram node to `{{ $json.messageChunk }}`

#### 5.3 Patch "Send Monthly Summary"

Same process as 5.2, using node name `Batch Monthly Summary`.

#### 5.4 Patch "Format Parcelas Response"

1. Add a Code node `Batch Parcelas` between `Format Parcelas Response` and `Reply user - query result`
2. Note: if `Format Parcelas Response` also feeds into `Reply user - query result`, the batching node at 5.1 already covers it -- verify the connection path

### Step-by-Step: Option B (Sub-Workflow)

#### 5.5 Create the Sub-Workflow

1. In n8n, create a new workflow: **"Send Telegram Batched"**
2. Add nodes in this order:
   - **Execute Workflow Trigger** (start node) -- receives `message`, `chatId`, `reply_to_message_id`
   - **Code node** (`Message Batcher`) -- paste the batcher code from Section 3
   - **Telegram node** (`Send Batched Message`):
     - Operation: Send Message
     - Chat ID: `{{ $json.chatId }}`
     - Text: `{{ $json.messageChunk }}`
     - Parse Mode: HTML
3. Save and activate the sub-workflow

#### 5.6 Replace Main Workflow Telegram Nodes

For each high-risk Telegram send node in the main workflow:

1. Note the incoming connections and the expressions used for `text` and `chatId`
2. Delete (or disable) the Telegram send node
3. Add an **Execute Sub-Workflow** node in its place:
   - Workflow: Select "Send Telegram Batched"
   - Input data mapping:
     ```json
     {
       "message": "{{ <original text expression> }}",
       "chatId": "{{ <original chatId expression> }}"
     }
     ```
4. Reconnect the incoming wires

### Rate Limiting Consideration

Telegram imposes rate limits (~30 messages per second to the same chat). For very long messages that split into many chunks, add a **Wait node** (200ms) inside the sub-workflow between the Code node and the Telegram node, or use n8n's built-in **batch settings** on the Telegram node to limit throughput. In practice, Financial Tracker messages are unlikely to exceed 5-6 chunks, so this is a low risk.

### Testing

1. **Unit test the batcher**: Create a test Code node with a hardcoded message over 4096 characters. Verify:
   - Output has multiple items
   - Each `messageChunk` is under 4096 characters
   - HTML tags are properly closed/reopened across chunks
   - Pagination indicators appear (`(1/N)`, `(2/N)`, etc.)
   - Content is complete (no lost text)

2. **Integration test**: Trigger a query that returns many transactions (e.g., "show all expenses this month" with 30+ entries). Verify:
   - All messages arrive in Telegram in order
   - Formatting (bold, italic, links) is preserved
   - Pagination is shown
   - No Telegram API errors in n8n execution log

3. **Edge cases to test**:
   - Message exactly at 4096 characters
   - Message with deeply nested HTML (`<b><i><u>...</u></i></b>`)
   - Message with no good split points (single very long line)
   - Empty message (should pass through without error)
   - Message with section separators (`━━━`) near the split boundary

---

## 6. Summary of Changes

| What | Where | Action |
|------|-------|--------|
| Message Batcher code | New Code node(s) or sub-workflow | Add |
| `Reply user - query result` | Main workflow | Insert batcher before; update Text field |
| `Send Weekly Summary` | Main workflow | Insert batcher before; update Text field |
| `Send Monthly Summary` | Main workflow | Insert batcher before; update Text field |
| `Format Parcelas Response` path | Main workflow | Insert batcher before send node; update Text field |
| Low-risk nodes (smalltalk, errors, etc.) | Main workflow | No changes needed -- messages are short |

**Estimated effort**: 1-2 hours for Option A (inline), 1 hour for Option B (sub-workflow) after initial setup.
