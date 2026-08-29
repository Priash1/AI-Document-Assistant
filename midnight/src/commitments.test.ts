import assert from 'node:assert/strict';
import { randomBytes } from 'node:crypto';
import { describe, it } from 'node:test';
import {
  authorizationCommitment,
  authorizationNullifier,
  bytesToHex,
  deriveDocumentOpening,
  deriveOwnerSecret,
  documentCommitment,
  hexToBytes32,
  ownerCommitment,
} from './commitments';

describe('PrivateDocs commitment helpers', () => {
  it('matches stable 32-byte commitment boundaries', () => {
    const owner = deriveOwnerSecret('01'.repeat(32));
    const document = hexToBytes32('ab'.repeat(32), 'document');
    const query = hexToBytes32('cd'.repeat(32), 'query');
    const documentOpening = deriveDocumentOpening(owner, document);
    const authorizationOpening = new Uint8Array(Buffer.alloc(32, 7));

    const docCommitment = documentCommitment(document, documentOpening);
    const authorization = authorizationCommitment(
      document,
      query,
      authorizationOpening,
    );
    const nullifier = authorizationNullifier(authorization);

    for (const value of [
      owner,
      ownerCommitment(owner),
      documentOpening,
      docCommitment,
      authorization,
      nullifier,
    ]) {
      assert.equal(value.length, 32);
      assert.match(bytesToHex(value), /^[0-9a-f]{64}$/);
    }
  });

  it('binds authorization to document, query and fresh opening', () => {
    const docA = randomBytes(32);
    const docB = randomBytes(32);
    const queryA = randomBytes(32);
    const queryB = randomBytes(32);
    const openingA = randomBytes(32);
    const openingB = randomBytes(32);

    const baseline = bytesToHex(authorizationCommitment(docA, queryA, openingA));
    assert.notEqual(
      baseline,
      bytesToHex(authorizationCommitment(docB, queryA, openingA)),
    );
    assert.notEqual(
      baseline,
      bytesToHex(authorizationCommitment(docA, queryB, openingA)),
    );
    assert.notEqual(
      baseline,
      bytesToHex(authorizationCommitment(docA, queryA, openingB)),
    );
  });

  it('produces deterministic document commitments and nullifiers', () => {
    const owner = deriveOwnerSecret('ff'.repeat(32));
    const document = randomBytes(32);
    const query = randomBytes(32);
    const opening = randomBytes(32);

    assert.deepEqual(
      deriveDocumentOpening(owner, document),
      deriveDocumentOpening(owner, document),
    );
    const authorization = authorizationCommitment(document, query, opening);
    assert.deepEqual(
      authorizationNullifier(authorization),
      authorizationNullifier(authorization),
    );
  });

  it('rejects malformed hexadecimal inputs', () => {
    assert.throws(() => hexToBytes32('AA'.repeat(32)), /lowercase hexadecimal/);
    assert.throws(() => hexToBytes32('a'.repeat(63)), /exactly 32/);
  });
});
