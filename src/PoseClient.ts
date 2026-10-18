import type { Joint } from './pose';
export type PoseFrame = { image: Joint[]; world: Joint[]; inferenceMs: number };
type Pending = { resolve: (value: any) => void; reject: (error: Error) => void; timer: ReturnType<typeof setTimeout> };
export class PoseClient {
  private worker: Worker | null = null;
  private pending = new Map<number, Pending>();
  private id = 0;
  async start() {
    if (!window.Worker || !window.createImageBitmap || !window.OffscreenCanvas) throw new Error('This browser cannot run the joint tracker. Open the app in a current Chrome or Edge browser.');
    this.worker = new Worker('/assets/pose-worker.js');
    this.worker.onmessage = ({ data }) => {
      const pending = this.pending.get(data.id); if (!pending) return;
      clearTimeout(pending.timer); this.pending.delete(data.id);
      data.error ? pending.reject(new Error('Joint tracker: ' + data.error)) : pending.resolve(data);
    };
    this.worker.onerror = () => this.close('Could not load the local joint tracker. Restart the app and reload this page.');
    try { await this.request({ type: 'init' }, [], 45000); }
    catch (error) { this.close(); throw error; }
  }
  private request(payload: Record<string, unknown>, transfer: Transferable[] = [], timeout = 8000): Promise<any> {
    if (!this.worker) return Promise.reject(new Error('Joint tracker is closed.'));
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id); reject(new Error('Joint tracker stopped responding. Restart tracking to recover.')); this.close();
      }, timeout);
      this.pending.set(id, { resolve, reject, timer });
      try { this.worker!.postMessage({ ...payload, id }, transfer); }
      catch (error) { clearTimeout(timer); this.pending.delete(id); reject(error); }
    });
  }
  async detect(source: ImageBitmapSource, timestamp: number): Promise<PoseFrame> {
    const frame = await createImageBitmap(source);
    if (!this.worker) { frame.close(); throw new Error('Joint tracker is closed.'); }
    try { return await this.request({ type: 'frame', frame, timestamp }, [frame]); }
    finally { frame.close(); }
  }
  close(message = 'Tracking stopped.') {
    this.worker?.terminate(); this.worker = null;
    for (const p of this.pending.values()) { clearTimeout(p.timer); p.reject(new Error(message)); }
    this.pending.clear();
  }
}
