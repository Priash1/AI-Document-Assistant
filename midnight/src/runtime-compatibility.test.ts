import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  ChargedState as CompactChargedState,
  StateValue as CompactStateValue,
} from '@midnight-ntwrk/compact-runtime';
import {
  ChargedState as ProtocolChargedState,
  StateValue as ProtocolStateValue,
} from '@midnight-ntwrk/midnight-js-protocol/onchain-runtime';

describe('Midnight runtime compatibility', () => {
  it('uses one onchain runtime class identity across Compact and Midnight.js', () => {
    assert.strictEqual(CompactStateValue, ProtocolStateValue);
    assert.strictEqual(CompactChargedState, ProtocolChargedState);
  });
});
