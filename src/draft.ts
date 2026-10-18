import type { RecordedFrame } from './data';
import type { ExerciseType } from './pose';
export type SessionDraft = { client_id: string; exercise: ExerciseType; date: string; reps: number; duration: number; target: number; source: 'camera'; frames: RecordedFrame[] };
function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('motionai-recovery', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('draft');
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}
async function transaction<T>(mode: IDBTransactionMode, action: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const database = await open();
  return new Promise((resolve, reject) => {
    const tx = database.transaction('draft', mode), request = action(tx.objectStore('draft'));
    tx.oncomplete = () => { database.close(); resolve(request.result); };
    tx.onerror = () => { database.close(); reject(tx.error); };
    tx.onabort = () => { database.close(); reject(tx.error || new Error('Local recovery storage unavailable.')); };
  });
}
// One chain prevents an older autosave from resurrecting a finished or discarded recording.
let writes: Promise<unknown> = Promise.resolve();
export const readDraft = () => transaction<SessionDraft | undefined>('readonly', store => store.get('current'));
export function writeDraft(draft: SessionDraft | null) {
  writes = writes.catch(() => {}).then(() => draft ? transaction('readwrite', s => s.put(draft, 'current')) : transaction('readwrite', s => s.delete('current')));
  return writes;
}
