import { DecimalPipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { errorMessage } from '../../core/errors';
import { UploadProgress, VideoService } from '../../core/video.service';

@Component({
  selector: 'app-upload',
  imports: [FormsModule, DecimalPipe],
  host: { '(window:beforeunload)': 'onBeforeUnload($event)' },
  template: `
    <div class="card">
      <h2>Загрузка видео</h2>
      <form class="form" (ngSubmit)="submit()">
        <label>
          Название
          <input name="title" [(ngModel)]="title" required [disabled]="busy()" />
        </label>
        <label>
          Описание
          <textarea name="description" rows="3" [(ngModel)]="description" [disabled]="busy()"></textarea>
        </label>
        <label>
          Файл
          <input type="file" accept="video/*" (change)="onFile($event)" [disabled]="busy()" />
        </label>

        @if (progress(); as p) {
          <progress [value]="p.sentBytes" [max]="p.totalBytes"></progress>
          <div class="muted">
            {{ percent() | number: '1.0-0' }}% ·
            {{ p.sentBytes / mb | number: '1.0-1' }} / {{ p.totalBytes / mb | number: '1.0-1' }} МБ
          </div>
        }
        @if (error()) {
          <div class="error">{{ error() }}</div>
        }
        <div>
          <button class="primary" type="submit" [disabled]="busy() || !file() || !title.trim()">
            {{ busy() ? 'Загружается…' : 'Загрузить' }}
          </button>
        </div>
      </form>
    </div>
  `,
  styles: `
    progress {
      width: 100%;
      height: 10px;
    }
  `,
})
export class Upload {
  private readonly videoService = inject(VideoService);
  private readonly router = inject(Router);

  protected readonly mb = 1024 * 1024;
  protected title = '';
  protected description = '';
  protected readonly file = signal<File | null>(null);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly progress = signal<UploadProgress | null>(null);
  protected readonly percent = computed(() => {
    const p = this.progress();
    return p && p.totalBytes > 0 ? (p.sentBytes / p.totalBytes) * 100 : 0;
  });

  protected onFile(event: Event): void {
    const file = (event.target as HTMLInputElement).files?.[0] ?? null;
    this.file.set(file);
    if (file && !this.title.trim()) {
      this.title = file.name.replace(/\.[^.]+$/, '');
    }
  }

  protected async submit(): Promise<void> {
    const file = this.file();
    if (!file) {
      return;
    }
    if (file.size === 0) {
      this.error.set('Файл пустой');
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    try {
      const video = await this.videoService.upload(file, this.title.trim(), this.description, (p) =>
        this.progress.set(p),
      );
      this.busy.set(false);
      await this.router.navigate(['/videos', video.id]);
    } catch (err) {
      this.error.set(errorMessage(err));
      this.busy.set(false);
    }
  }

  /** Сервер пока не умеет докачивать после перезагрузки страницы — предупреждаем. */
  protected onBeforeUnload(event: BeforeUnloadEvent): void {
    if (this.busy()) {
      event.preventDefault();
    }
  }
}
