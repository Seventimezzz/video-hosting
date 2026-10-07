import {
  Component,
  DestroyRef,
  ElementRef,
  effect,
  inject,
  input,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import Hls from 'hls.js';
import { interval } from 'rxjs';

import { errorMessage } from '../../core/errors';
import { IN_PROGRESS_STATUSES, Video } from '../../core/models';
import { VideoService } from '../../core/video.service';

const POLL_INTERVAL_MS = 3000;
const AUTO_LEVEL = -1;

interface Level {
  index: number;
  label: string;
}

@Component({
  selector: 'app-video-player',
  imports: [RouterLink],
  template: `
    <p><a routerLink="/videos">← К списку</a></p>
    @if (error()) {
      <p class="error">{{ error() }}</p>
    }
    @if (video(); as v) {
      <h2>{{ v.title }} <span class="status" [class]="v.status">{{ v.status }}</span></h2>
      @if (v.description) {
        <p class="muted">{{ v.description }}</p>
      }

      @switch (v.status) {
        @case ('ready') {
          @if (v.playback_url) {
            <video #player controls playsinline></video>
            @if (levels().length > 0) {
              <div class="levels">
                <span class="muted">Качество:</span>
                <button [class.primary]="selectedLevel() === autoLevel" (click)="selectLevel(autoLevel)">
                  Авто
                </button>
                @for (level of levels(); track level.index) {
                  <button [class.primary]="selectedLevel() === level.index" (click)="selectLevel(level.index)">
                    {{ level.label }}
                  </button>
                }
                @if (playingLevel(); as playing) {
                  <span class="muted">сейчас играет: {{ playing }}</span>
                }
              </div>
            }
          } @else {
            <p class="error">Видео готово, но API не вернул playback_url.</p>
          }
        }
        @case ('failed') {
          <p class="error">Обработка завершилась ошибкой.</p>
        }
        @default {
          <p class="muted">Видео ещё не готово (статус: {{ v.status }}). Страница обновится сама.</p>
        }
      }
    } @else if (!error()) {
      <p class="muted">Загрузка…</p>
    }
  `,
  styles: `
    video {
      width: 100%;
      max-height: 70vh;
      background: #000;
      border-radius: 8px;
    }
    .levels {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      margin-top: 12px;
    }
  `,
})
export class VideoPlayer {
  /** :id из маршрута, приходит через withComponentInputBinding. */
  readonly id = input.required<string>();

  private readonly videoService = inject(VideoService);
  private readonly playerRef = viewChild<ElementRef<HTMLVideoElement>>('player');

  protected readonly autoLevel = AUTO_LEVEL;
  protected readonly video = signal<Video | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly levels = signal<Level[]>([]);
  protected readonly selectedLevel = signal(AUTO_LEVEL);
  protected readonly playingLevel = signal<string | null>(null);

  private hls: Hls | null = null;
  private attachedUrl: string | null = null;

  constructor() {
    effect(() => {
      const id = Number(this.id());
      untracked(() => this.load(id));
    });

    // Пока воркер транскодирует — опрашиваем статус.
    interval(POLL_INTERVAL_MS)
      .pipe(takeUntilDestroyed())
      .subscribe(() => {
        const v = this.video();
        if (v && (IN_PROGRESS_STATUSES.includes(v.status) || v.status === 'uploading')) {
          this.load(v.id);
        }
      });

    // <video> появляется в DOM только при status === 'ready', поэтому ждём его через viewChild.
    effect(() => {
      const el = this.playerRef()?.nativeElement;
      const url = this.video()?.playback_url;
      if (el && url && url !== this.attachedUrl) {
        untracked(() => this.attach(el, url));
      }
    });

    inject(DestroyRef).onDestroy(() => this.hls?.destroy());
  }

  private async load(id: number): Promise<void> {
    try {
      this.video.set(await this.videoService.get(id));
      this.error.set(null);
    } catch (err) {
      this.error.set(errorMessage(err));
    }
  }

  private attach(el: HTMLVideoElement, url: string): void {
    this.hls?.destroy();
    this.attachedUrl = url;

    if (Hls.isSupported()) {
      // Chrome/Firefox/Edge: нативного HLS нет, hls.js сам качает плейлисты и сегменты
      // и скармливает их <video> через Media Source Extensions.
      const hls = new Hls();
      this.hls = hls;
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        this.levels.set(
          hls.levels
            .map((level, index) => ({ index, label: `${level.height}p`, height: level.height }))
            .sort((a, b) => b.height - a.height)
            .map(({ index, label }) => ({ index, label })),
        );
      });
      hls.on(Hls.Events.LEVEL_SWITCHED, (_event, data) => {
        const level = hls.levels[data.level];
        this.playingLevel.set(level ? `${level.height}p` : null);
      });
      hls.on(Hls.Events.ERROR, (_event, data) => {
        if (data.fatal) {
          this.error.set(`Ошибка плеера: ${data.type} / ${data.details}`);
        }
      });
      hls.loadSource(url);
      hls.attachMedia(el);
    } else if (el.canPlayType('application/vnd.apple.mpegurl')) {
      // Safari (и iOS) умеют HLS нативно — переключение качеств делает сам браузер.
      el.src = url;
    } else {
      this.error.set('Браузер не поддерживает HLS');
    }
  }

  protected selectLevel(index: number): void {
    if (!this.hls) {
      return;
    }
    // -1 возвращает автоматический выбор (ABR); конкретный индекс фиксирует качество.
    this.hls.currentLevel = index;
    this.selectedLevel.set(index);
  }
}
