import { createHash, createHmac } from 'node:crypto';
import {
  CompactTypeBytes,
  CompactTypeVector,
  persistentCommit,
  persistentHash,
} from '@midnight-ntwrk/compact-runtime';

const HEX_32 = /^[0-9a-f]{64}$/;
const BYTES_32 = new CompactTypeBytes(32);
const TWO_BYTES_32 = new CompactTypeVector(2, BYTES_32);

function paddedDomain(label: string): Uint8Array {
  const encoded = Buffer.from(label, 'utf8');
  if (encoded.length > 32) {
    throw new Error(`Domain label exceeds 32 bytes: ${label}`);
  }
  const result = new Uint8Array(32);
  result.set(encoded);
  return result;
}

const OWNER_DOMAIN = paddedDomain('privatedocs:owner:v1:');
const DOCUMENT_OPENING_DOMAIN = Buffer.from(
  'privatedocs:document-opening:v1\0',
  'utf8',
);
const NULLIFIER_DOMAIN = paddedDomain('privatedocs:nullifier:v1:');

export function bytesToHex(value: Uint8Array): string {
  return Buffer.from(value).toString('hex');
}

export function hexToBytes32(value: string, label = 'digest'): Uint8Array {
  if (!HEX_32.test(value)) {
    throw new Error(`${label} must be exactly 32 lowercase hexadecimal bytes`);
  }
  return new Uint8Array(Buffer.from(value, 'hex'));
}

export function deriveOwnerSecret(walletSeedHex: string): Uint8Array {
  const normalized = walletSeedHex.trim().toLowerCase();
  if (!/^[0-9a-f]{32,256}$/.test(normalized) || normalized.length % 2 !== 0) {
    throw new Error('Wallet seed must be an even-length hexadecimal value');
  }
  return new Uint8Array(
    createHash('sha256')
      .update('privatedocs:owner-secret:v1\0', 'utf8')
      .update(Buffer.from(normalized, 'hex'))
      .digest(),
  );
}

export function ownerCommitment(ownerSecret: Uint8Array): Uint8Array {
  return persistentHash(TWO_BYTES_32, [OWNER_DOMAIN, assertBytes32(ownerSecret, 'owner secret')]);
}

// A keyed, domain-separated derivation gives each document a stable 32-byte
// commitment opening without persisting the PDF or its digest in bridge state.
export function deriveDocumentOpening(
  ownerSecret: Uint8Array,
  documentDigest: Uint8Array,
): Uint8Array {
  return new Uint8Array(
    createHmac('sha256', assertBytes32(ownerSecret, 'owner secret'))
      .update(DOCUMENT_OPENING_DOMAIN)
      .update(assertBytes32(documentDigest, 'document digest'))
      .digest(),
  );
}

export function documentCommitment(
  documentDigest: Uint8Array,
  documentOpening: Uint8Array,
): Uint8Array {
  return persistentCommit(
    BYTES_32,
    assertBytes32(documentDigest, 'document digest'),
    assertBytes32(documentOpening, 'document opening'),
  );
}

export function authorizationCommitment(
  documentDigest: Uint8Array,
  queryDigest: Uint8Array,
  authorizationOpening: Uint8Array,
): Uint8Array {
  return persistentCommit(
    TWO_BYTES_32,
    [
      assertBytes32(documentDigest, 'document digest'),
      assertBytes32(queryDigest, 'query digest'),
    ],
    assertBytes32(authorizationOpening, 'authorization opening'),
  );
}

export function authorizationNullifier(authorization: Uint8Array): Uint8Array {
  return persistentHash(TWO_BYTES_32, [
    NULLIFIER_DOMAIN,
    assertBytes32(authorization, 'authorization commitment'),
  ]);
}

function assertBytes32(value: Uint8Array, label: string): Uint8Array {
  if (!(value instanceof Uint8Array) || value.length !== 32) {
    throw new Error(`${label} must contain exactly 32 bytes`);
  }
  return value;
}
