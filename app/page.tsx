'use client';

import Image from 'next/image';
import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';

const situations = [
  ['A product that has not been built yet', 'Idea, new direction or an untested business model.'],
  ['A product that does not perform', 'The experience exists, but the expected result does not.'],
  ['A business that has outgrown its digital layer', 'The site, brand or system no longer matches the company.'],
  ['A problem with no obvious category', 'Something is wrong, but the source is still unclear.'],
];

const process = [
  ['Receive', 'We read the situation as you describe it.'],
  ['Observe', 'We examine the available product and material.'],
  ['Reply', 'We respond the same day with first observations.'],
  ['Audit', 'We agree on the depth of further analysis.'],
  ['Model', 'We develop routes and define what happens first.'],
  ['Build', 'We take the selected route into implementation.'],
];

const method = [
  ['Observe', 'Business, product, users, data and constraints.', 'INPUT'],
  ['Refract', 'Commercial, product, visual and technical components.', 'DECOMPOSITION'],
  ['Model', 'Structures, scenarios, prototypes and solution routes.', 'STRUCTURE'],
  ['Experiment', 'Critical assumptions tested before full implementation.', 'VALIDATION'],
  ['Build', 'Design, development, integration and launch.', 'IMPLEMENTATION'],
  ['Evolve', 'Support, observation and continuous improvement.', 'EVOLUTION'],
];

const capabilities = [
  ['Product', 'Research, product logic, business models and validation.', 'We turn an initial idea or an underperforming product into a model that can be examined, challenged and built.', ['Problem framing', 'Business model', 'Validation route']],
  ['Web', 'Marketing sites, platforms, services and interactive experiences.', 'We connect product structure, communication and technology so the website performs as part of the business.', ['Architecture', 'Interface system', 'Development']],
  ['Mobile', 'Product concepts, interfaces, applications and supporting systems.', 'We define what the application must change for users and the business before committing to full implementation.', ['Product concept', 'UX and UI', 'Application build']],
  ['Brand', 'Positioning, identity, offers and communication systems.', 'We align the way the product looks and speaks with the value it must communicate and the market it enters.', ['Positioning', 'Identity', 'Offer system']],
  ['Marketing', 'Acquisition models, campaigns, content and analytics.', 'We design the path from attention to action around the product rather than treating promotion as a separate layer.', ['Acquisition model', 'Campaign system', 'Measurement']],
  ['Technology', 'Frontend, backend, integrations and technical support.', 'We select and assemble the technical system around the actual constraints, required speed and future development.', ['System design', 'Integrations', 'Ongoing support']],
] as const;

const briefPrompts = [
  ['We have an idea', 'We have an idea, but we are not yet sure how to turn it into a working product.'],
  ['It is not performing', 'The product exists, but it is not producing the result we expected.'],
  ['It needs to be rebuilt', 'The current product no longer fits the business and may need to be rebuilt.'],
  ['We are not sure', 'Something is not working, but we are not yet sure where the real problem is.'],
];

const MAX_BRIEF_FILES = 6;
const MAX_BRIEF_FILE_SIZE = 10 * 1024 * 1024;
const MAX_BRIEF_TOTAL_SIZE = 30 * 1024 * 1024;
const blockedBriefExtensions = /\.(exe|msi|bat|cmd|com|scr|ps1|jar)$/i;

type BriefDraft = {
  message: string;
  productLink: string;
  noProduct: boolean;
  name: string;
  telegram: string;
  email: string;
  consent: boolean;
};

const emptyBriefDraft: BriefDraft = {
  message: '',
  productLink: '',
  noProduct: false,
  name: '',
  telegram: '',
  email: '',
  consent: false,
};

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function RefractionCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext('2d');
    if (!context) return;
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let pointerClientX = window.innerWidth * 0.16;
    let pointerClientY = window.innerHeight * 0.58;
    let sourceX = pointerClientX;
    let sourceY = pointerClientY;
    let scheduled = 0;

    const draw = () => {
      scheduled = 0;
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      const canvasRect = canvas.getBoundingClientRect();
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
        canvas.width = Math.round(width * ratio);
        canvas.height = Math.round(height * ratio);
      }
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, width, height);

      const prism = document.querySelector<HTMLElement>('[data-hero-prism]');
      if (!prism) return;
      const prismRect = prism.getBoundingClientRect();
      const prismX = prismRect.left + prismRect.width * 0.48 - canvasRect.left;
      const prismY = prismRect.top + prismRect.height * 0.50 - canvasRect.top;

      const targetX = Math.max(0, Math.min(width, pointerClientX - canvasRect.left));
      const targetY = Math.max(0, Math.min(height, pointerClientY - canvasRect.top));
      const easing = reducedMotion ? 1 : 0.15;
      sourceX += (targetX - sourceX) * easing;
      sourceY += (targetY - sourceY) * easing;

      const incomingX = prismX - sourceX;
      const incomingY = prismY - sourceY;
      const baseAngle = Math.atan2(incomingY, incomingX);
      const travel = Math.hypot(width, height) * 1.25;

      const strokeRay = (x1: number, y1: number, x2: number, y2: number, rgb: string, colored = true) => {
        const gradient = context.createLinearGradient(x1, y1, x2, y2);
        if (colored) {
          gradient.addColorStop(0, 'rgba(255,255,255,.78)');
          gradient.addColorStop(.08, `rgba(${rgb},.62)`);
          gradient.addColorStop(.55, `rgba(${rgb},.27)`);
          gradient.addColorStop(1, `rgba(${rgb},.025)`);
        } else {
          gradient.addColorStop(0, 'rgba(255,255,255,.28)');
          gradient.addColorStop(.64, 'rgba(255,255,255,.52)');
          gradient.addColorStop(1, 'rgba(255,255,255,.88)');
        }

        context.save();
        context.globalCompositeOperation = 'lighter';
        context.lineCap = 'round';
        context.strokeStyle = gradient;
        context.shadowColor = colored ? `rgba(${rgb},.48)` : 'rgba(255,255,255,.42)';
        context.shadowBlur = colored ? 22 : 15;
        context.globalAlpha = colored ? .42 : .36;
        context.lineWidth = colored ? 8 : 6;
        context.beginPath();
        context.moveTo(x1, y1);
        context.lineTo(x2, y2);
        context.stroke();

        context.globalAlpha = 1;
        context.shadowBlur = colored ? 8 : 5;
        context.lineWidth = colored ? 1.15 : 1.05;
        context.beginPath();
        context.moveTo(x1, y1);
        context.lineTo(x2, y2);
        context.stroke();
        context.restore();
      };

      strokeRay(sourceX, sourceY, prismX, prismY, '255,255,255', false);

      const rays = [
        ['85,196,255', -0.18],
        ['130,120,255', -0.065],
        ['206,103,235', 0.055],
        ['239,118,180', 0.17],
      ] as const;

      rays.forEach(([rgb, offset]) => {
        const angle = baseAngle + offset;
        const endX = prismX + Math.cos(angle) * travel;
        const endY = prismY + Math.sin(angle) * travel;
        strokeRay(prismX, prismY, endX, endY, rgb);
      });

      const prismGlow = context.createRadialGradient(prismX, prismY, 0, prismX, prismY, Math.min(width * 0.15, 210));
      prismGlow.addColorStop(0, 'rgba(255,255,255,.16)');
      prismGlow.addColorStop(.18, 'rgba(130,120,255,.13)');
      prismGlow.addColorStop(1, 'rgba(5,5,6,0)');
      context.fillStyle = prismGlow;
      context.fillRect(prismX - 230, prismY - 230, 460, 460);

      const sourceGlow = context.createRadialGradient(sourceX, sourceY, 0, sourceX, sourceY, 52);
      sourceGlow.addColorStop(0, 'rgba(255,255,255,.16)');
      sourceGlow.addColorStop(1, 'rgba(5,5,6,0)');
      context.fillStyle = sourceGlow;
      context.fillRect(sourceX - 60, sourceY - 60, 120, 120);
      context.fillStyle = 'rgba(255,255,255,.74)';
      context.beginPath();
      context.arc(sourceX, sourceY, 2.3, 0, Math.PI * 2);
      context.fill();

      context.fillStyle = 'rgba(255,255,255,.82)';
      context.beginPath();
      context.arc(prismX, prismY, 2.7, 0, Math.PI * 2);
      context.fill();
      context.globalCompositeOperation = 'source-over';

      if (Math.abs(targetX - sourceX) > .2 || Math.abs(targetY - sourceY) > .2) schedule();
    };

    const schedule = () => {
      if (!scheduled) scheduled = requestAnimationFrame(draw);
    };
    const onPointer = (event: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      if (event.clientY < rect.top || event.clientY > rect.bottom) return;
      pointerClientX = event.clientX;
      pointerClientY = event.clientY;
      schedule();
    };

    schedule();
    window.addEventListener('resize', schedule);
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('pointermove', onPointer, { passive: true });
    return () => {
      if (scheduled) cancelAnimationFrame(scheduled);
      window.removeEventListener('resize', schedule);
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('pointermove', onPointer);
    };
  }, []);

  return <canvas className="hero-canvas" ref={canvasRef} aria-hidden="true" />;
}

function OpticalNarrative() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext('2d');
    if (!canvas || !context) return;

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let pointerTargetX = window.innerWidth * 0.5;
    let pointerTargetY = window.innerHeight * 0.42;
    let pointerX = pointerTargetX;
    let pointerY = pointerTargetY;
    let rayEnergy = 1;
    let rayEnergyTarget = 1;
    let idleTimer = 0;
    let scheduled = 0;

    const clamp = (value: number, min = 0, max = 1) => Math.max(min, Math.min(max, value));

    const resize = () => {
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
        canvas.width = Math.round(width * ratio);
        canvas.height = Math.round(height * ratio);
      }
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      return { width, height };
    };

    const schedule = () => {
      if (!scheduled) scheduled = requestAnimationFrame(draw);
    };

    const draw = () => {
      scheduled = 0;
      const { width, height } = resize();
      context.clearRect(0, 0, width, height);

      const sections = Array.from(document.querySelectorAll<HTMLElement>('[data-optical-state]'));
      const viewportCenter = height * 0.5;
      const active = sections
        .map((section) => ({ section, rect: section.getBoundingClientRect() }))
        .filter(({ rect }) => rect.bottom > 0 && rect.top < height)
        .sort((a, b) => Math.abs((a.rect.top + a.rect.bottom) / 2 - viewportCenter) - Math.abs((b.rect.top + b.rect.bottom) / 2 - viewportCenter))[0];

      if (!active) return;

      const state = active.section.dataset.opticalState || '';
      const dark = active.section.dataset.opticalTheme === 'dark';
      const easing = reducedMotion ? 1 : 0.14;
      pointerX += (pointerTargetX - pointerX) * easing;
      pointerY += (pointerTargetY - pointerY) * easing;
      rayEnergy += (rayEnergyTarget - rayEnergy) * (reducedMotion ? 1 : .11);

      const rawTargets = Array.from(active.section.querySelectorAll<HTMLElement>('[data-ray-target]'));
      const targets = rawTargets
        .map((element) => ({ element, rect: element.getBoundingClientRect() }))
        .filter(({ rect }) => rect.bottom > -24 && rect.top < height + 24)
        .slice(0, 6);
      const pointedElement = document.elementFromPoint(pointerTargetX, pointerTargetY) as HTMLElement | null;
      const pointedTarget = pointedElement?.closest<HTMLElement>('[data-ray-target]') || null;
      const activeTargetIndex = pointedTarget && active.section.contains(pointedTarget)
        ? targets.findIndex(({ element }) => element === pointedTarget)
        : -1;

      const stateOrder = ['diagnosis', 'situations', 'process', 'audit', 'method', 'capabilities', 'experiments', 'convergence'];
      const paletteOffset = Math.max(0, stateOrder.indexOf(state));
      const palette = dark
        ? [
            ['85,196,255', '.58'],
            ['130,120,255', '.56'],
            ['239,118,208', '.48'],
            ['245,245,242', '.32'],
          ]
        : [
            ['25,142,199', '.34'],
            ['91,76,214', '.32'],
            ['185,63,150', '.27'],
            ['16,16,19', '.19'],
          ];

      const anchorFor = (element: HTMLElement, rect: DOMRect): [number, number] => {
        const anchor = element.dataset.rayAnchor || 'center';
        if (anchor === 'top-left') return [rect.left, rect.top];
        if (anchor === 'top-right') return [rect.right, rect.top];
        if (anchor === 'bottom-left') return [rect.left, rect.bottom];
        if (anchor === 'bottom-right') return [rect.right, rect.bottom];
        if (anchor === 'left') return [rect.left, rect.top + rect.height / 2];
        if (anchor === 'right') return [rect.right, rect.top + rect.height / 2];
        return [rect.left + rect.width / 2, rect.top + rect.height / 2];
      };

      const drawRay = (endX: number, endY: number, index: number, intensity = 1) => {
        const [rgb, strength] = palette[(index + paletteOffset) % palette.length];
        const weightedStrength = Number(strength) * intensity;
        const core = context.createLinearGradient(pointerX, pointerY, endX, endY);
        core.addColorStop(0, dark ? `rgba(255,255,255,${.78 * intensity})` : `rgba(${rgb},${.56 * intensity})`);
        core.addColorStop(.08, `rgba(${rgb},${weightedStrength})`);
        core.addColorStop(.58, `rgba(${rgb},${(dark ? .22 : .14) * intensity})`);
        core.addColorStop(1, `rgba(${rgb},${(dark ? .44 : .26) * intensity})`);

        context.save();
        context.globalCompositeOperation = dark ? 'lighter' : 'source-over';
        context.lineCap = 'round';
        context.strokeStyle = core;
        context.shadowColor = `rgba(${rgb},${dark ? '.42' : '.30'})`;
        context.shadowBlur = dark ? 20 : 15;
        context.globalAlpha = (dark ? .42 : .32) * intensity;
        context.lineWidth = (dark ? 7 : 6) * Math.max(.45, intensity);
        context.beginPath();
        context.moveTo(pointerX, pointerY);
        context.lineTo(endX, endY);
        context.stroke();

        context.shadowBlur = dark ? 8 : 6;
        context.globalAlpha = intensity;
        context.lineWidth = 1.05;
        context.beginPath();
        context.moveTo(pointerX, pointerY);
        context.lineTo(endX, endY);
        context.stroke();

        context.fillStyle = `rgba(${rgb},${(dark ? .68 : .42) * intensity})`;
        context.shadowBlur = dark ? 14 : 9;
        context.beginPath();
        context.arc(endX, endY, 2.2, 0, Math.PI * 2);
        context.fill();

        context.shadowBlur = 0;
        context.strokeStyle = `rgba(${rgb},${dark ? '.28' : '.17'})`;
        context.lineWidth = 1;
        context.strokeRect(endX - 5, endY - 5, 10, 10);
        context.restore();
      };

      const anchorPoints = targets.map(({ element, rect }) => anchorFor(element, rect));

      if (state === 'audit' && anchorPoints.length > 1) {
        context.save();
        context.strokeStyle = dark ? 'rgba(245,245,242,.075)' : 'rgba(16,16,19,.06)';
        context.setLineDash([2, 10]);
        context.beginPath();
        anchorPoints.forEach(([x, y], index) => {
          if (index === 0) context.moveTo(x, y);
          else context.lineTo(x, y);
        });
        context.stroke();
        context.restore();
      }

      anchorPoints.forEach(([x, y], index) => {
        const focusIntensity = activeTargetIndex < 0 ? .72 : index === activeTargetIndex ? 1 : .07;
        const intensity = focusIntensity * rayEnergy;
        drawRay(x, y, index, intensity);
      });

      context.save();
      context.globalAlpha = Math.max(.12, rayEnergy);
      const sourceGlow = context.createRadialGradient(pointerX, pointerY, 0, pointerX, pointerY, dark ? 70 : 54);
      sourceGlow.addColorStop(0, dark ? 'rgba(255,255,255,.16)' : 'rgba(130,120,255,.10)');
      sourceGlow.addColorStop(.25, dark ? 'rgba(130,120,255,.09)' : 'rgba(85,196,255,.055)');
      sourceGlow.addColorStop(1, 'rgba(0,0,0,0)');
      context.fillStyle = sourceGlow;
      context.fillRect(pointerX - 80, pointerY - 80, 160, 160);
      context.fillStyle = dark ? 'rgba(255,255,255,.72)' : 'rgba(38,32,92,.44)';
      context.beginPath();
      context.arc(pointerX, pointerY, 2.5, 0, Math.PI * 2);
      context.fill();
      context.restore();

      if (Math.abs(pointerTargetX - pointerX) > .2 || Math.abs(pointerTargetY - pointerY) > .2 || Math.abs(rayEnergyTarget - rayEnergy) > .006) schedule();
    };

    const onPointer = (event: PointerEvent) => {
      pointerTargetX = clamp(event.clientX, 0, window.innerWidth);
      pointerTargetY = clamp(event.clientY, 0, window.innerHeight);
      rayEnergyTarget = 1;
      window.clearTimeout(idleTimer);
      idleTimer = window.setTimeout(() => {
        rayEnergyTarget = .035;
        schedule();
      }, 760);
      schedule();
    };

    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    window.addEventListener('pointermove', onPointer, { passive: true });
    const targetResizeObserver = new ResizeObserver(schedule);
    document.querySelectorAll<HTMLElement>('[data-optical-state]').forEach((section) => targetResizeObserver.observe(section));
    idleTimer = window.setTimeout(() => {
      rayEnergyTarget = .035;
      schedule();
    }, 760);
    schedule();

    return () => {
      if (scheduled) cancelAnimationFrame(scheduled);
      window.clearTimeout(idleTimer);
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      window.removeEventListener('pointermove', onPointer);
      targetResizeObserver.disconnect();
    };
  }, []);

  return <canvas className="optical-narrative" ref={canvasRef} aria-hidden="true" />;
}

const navigationSections = [
  { id: 'top', marker: '00', label: 'Entry', theme: 'dark' },
  { id: 'approach', marker: '01', label: 'Diagnosis', theme: 'light' },
  { id: 'situations', marker: '02', label: 'Any stage', theme: 'light' },
  { id: 'process', marker: '03', label: 'What happens next', theme: 'light' },
  { id: 'audit', marker: '04', label: 'Audit', theme: 'dark' },
  { id: 'method', marker: '05', label: 'Method', theme: 'light' },
  { id: 'capabilities', marker: '06', label: 'Implementation', theme: 'light' },
  { id: 'experiments', marker: '07', label: 'Experiments', theme: 'light' },
  { id: 'contact', marker: '08', label: 'Start', theme: 'dark' },
] as const;

type SiteHeaderProps = { onOpenBrief: () => void };

function SiteHeader({ onOpenBrief }: SiteHeaderProps) {
  const [activeId, setActiveId] = useState('top');
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const targetLine = window.innerHeight * .34;
      const sections = navigationSections
        .map((item) => ({ item, element: document.getElementById(item.id) }))
        .filter((entry): entry is { item: typeof navigationSections[number]; element: HTMLElement } => Boolean(entry.element));
      const active = sections
        .map((entry) => ({ ...entry, rect: entry.element.getBoundingClientRect() }))
        .filter(({ rect }) => rect.bottom > 0 && rect.top < window.innerHeight)
        .sort((a, b) => Math.abs((a.rect.top + Math.min(a.rect.height, window.innerHeight) * .28) - targetLine) - Math.abs((b.rect.top + Math.min(b.rect.height, window.innerHeight) * .28) - targetLine))[0];
      if (active) setActiveId((current) => current === active.item.id ? current : active.item.id);
      const available = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
      const nextProgress = Math.min(1, Math.max(0, window.scrollY / available));
      setProgress((current) => Math.abs(current - nextProgress) > .002 ? nextProgress : current);
    };
    const schedule = () => {
      if (!frame) frame = window.requestAnimationFrame(update);
    };
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    const documentResizeObserver = new ResizeObserver(schedule);
    documentResizeObserver.observe(document.body);
    update();
    return () => {
      if (frame) window.cancelAnimationFrame(frame);
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      documentResizeObserver.disconnect();
    };
  }, []);

  const active = navigationSections.find((item) => item.id === activeId) || navigationSections[0];
  const approachActive = ['approach', 'situations', 'process', 'audit', 'method'].includes(activeId);

  return (
    <header className="site-header" data-theme={active.theme}>
      <nav className="nav shell" aria-label="Main navigation">
        <a className="brand" href="#top" aria-label="Refraction LAB home">
          <Image src="/logo.svg" width={31} height={27} alt="" priority />
          <span>REFRACTION</span><i>/</i><span>LAB</span>
        </a>
        <span className="nav-context" aria-live="polite"><b>{active.marker}</b><i>/</i>{active.label}</span>
        <div className="nav-links">
          <a className={approachActive ? 'active' : ''} aria-current={approachActive ? 'location' : undefined} href="#approach">Approach</a>
          <a className={activeId === 'capabilities' ? 'active' : ''} aria-current={activeId === 'capabilities' ? 'location' : undefined} href="#capabilities">Capabilities</a>
          <a className={activeId === 'experiments' ? 'active' : ''} aria-current={activeId === 'experiments' ? 'location' : undefined} href="#experiments">Experiments</a>
          <button className="nav-cta" type="button" onClick={onOpenBrief}>Start with the problem <span>↗</span></button>
        </div>
      </nav>
      <span className="page-progress" aria-hidden="true" style={{ transform: `scaleX(${progress})` }} />
    </header>
  );
}

type BriefModalProps = { open: boolean; onClose: () => void };

function BriefModal({ open, onClose }: BriefModalProps) {
  const [step, setStep] = useState(1);
  const [contactMethod, setContactMethod] = useState<'telegram' | 'email'>('telegram');
  const [status, setStatus] = useState<'idle' | 'sending' | 'success' | 'error'>('idle');
  const [error, setError] = useState('');
  const [fileError, setFileError] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [draft, setDraft] = useState<BriefDraft>(emptyBriefDraft);
  const [hydrated, setHydrated] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const messageRef = useRef<HTMLTextAreaElement>(null);
  const closeStateRef = useRef({ hasDraft: false, status: 'idle' as typeof status });

  const hasDraft = Boolean(
    draft.message.trim() || draft.productLink.trim() || draft.name.trim() ||
    draft.telegram.trim() || draft.email.trim() || draft.noProduct || draft.consent || files.length,
  );

  closeStateRef.current = { hasDraft, status };

  const requestClose = useCallback(() => {
    const closeState = closeStateRef.current;
    if (closeState.status !== 'success' && closeState.hasDraft) {
      const shouldClose = window.confirm('Your draft will be kept. Close the form for now?');
      if (!shouldClose) return;
    }
    if (closeState.status === 'success') setStatus('idle');
    onClose();
  }, [onClose]);

  useEffect(() => {
    try {
      const saved = window.sessionStorage.getItem('refraction-brief-draft');
      if (saved) {
        const parsed = JSON.parse(saved) as { draft?: Partial<BriefDraft>; step?: number; contactMethod?: 'telegram' | 'email' };
        setDraft({ ...emptyBriefDraft, ...parsed.draft, consent: false });
        setStep(Math.min(3, Math.max(1, parsed.step || 1)));
        if (parsed.contactMethod === 'telegram' || parsed.contactMethod === 'email') setContactMethod(parsed.contactMethod);
      }
    } catch {
      window.sessionStorage.removeItem('refraction-brief-draft');
    } finally {
      setHydrated(true);
    }
  }, []);

  useEffect(() => {
    if (!hydrated || status === 'success') return;
    window.sessionStorage.setItem('refraction-brief-draft', JSON.stringify({ draft: { ...draft, consent: false }, step, contactMethod }));
  }, [contactMethod, draft, hydrated, status, step]);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    const previousFocus = document.activeElement as HTMLElement | null;
    document.body.style.overflow = 'hidden';
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        requestClose();
        return;
      }
      if (event.key !== 'Tab' || !dialogRef.current) return;
      const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), textarea, input:not([type="hidden"]):not([disabled])'))
        .filter((element) => element.offsetParent !== null);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    requestAnimationFrame(() => {
      const firstField = dialogRef.current?.querySelector<HTMLElement>('textarea, input:not([type="hidden"]), button');
      firstField?.focus();
    });
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', onKey);
      previousFocus?.focus();
    };
  }, [open, requestClose]);

  useEffect(() => {
    if (!open) return;
    const focusTimer = window.requestAnimationFrame(() => {
      if (status === 'success') {
        dialogRef.current?.querySelector<HTMLElement>('.brief-success .button')?.focus();
        return;
      }
      const selector = step === 1 ? '#message' : step === 2 ? '#productLink' : '#contact';
      dialogRef.current?.querySelector<HTMLElement>(selector)?.focus();
    });
    return () => window.cancelAnimationFrame(focusTimer);
  }, [open, status, step]);

  if (!open) return null;

  const updateDraft = <Key extends keyof BriefDraft>(key: Key, value: BriefDraft[Key]) => {
    setDraft((current) => ({ ...current, [key]: value }));
  };

  const applyPrompt = (prompt: string) => {
    setDraft((current) => ({
      ...current,
      message: current.message.trim() ? `${current.message.trimEnd()}\n\n${prompt}` : prompt,
    }));
    requestAnimationFrame(() => {
      messageRef.current?.focus();
      const length = messageRef.current?.value.length || 0;
      messageRef.current?.setSelectionRange(length, length);
    });
  };

  const addFiles = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(event.currentTarget.files || []);
    event.currentTarget.value = '';
    setFileError('');
    if (!selected.length) return;

    const unique = selected.filter((file) => !files.some((existing) =>
      existing.name === file.name && existing.size === file.size && existing.lastModified === file.lastModified,
    ));
    const combined = [...files, ...unique];
    const blocked = unique.find((file) => blockedBriefExtensions.test(file.name));
    const oversized = unique.find((file) => file.size > MAX_BRIEF_FILE_SIZE);
    const totalSize = combined.reduce((sum, file) => sum + file.size, 0);

    if (blocked) return setFileError(`${blocked.name} is not an accepted file type.`);
    if (oversized) return setFileError(`${oversized.name} is larger than 10 MB.`);
    if (combined.length > MAX_BRIEF_FILES) return setFileError(`Attach no more than ${MAX_BRIEF_FILES} files.`);
    if (totalSize > MAX_BRIEF_TOTAL_SIZE) return setFileError('Attachments must be 30 MB or less in total.');
    setFiles(combined);
  };

  const removeFile = (fileToRemove: File) => {
    setFiles((current) => current.filter((file) => file !== fileToRemove));
    setFileError('');
  };

  const clearDraft = () => {
    if (hasDraft && !window.confirm('Clear the entire draft and all selected files?')) return;
    setDraft(emptyBriefDraft);
    setFiles([]);
    setFileError('');
    setError('');
    setStatus('idle');
    setStep(1);
    setContactMethod('telegram');
    window.sessionStorage.removeItem('refraction-brief-draft');
    requestAnimationFrame(() => messageRef.current?.focus());
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = formRef.current;
    if (!form) return;
    setStatus('sending');
    setError('');
    try {
      const formData = new FormData(form);
      formData.delete('files');
      files.forEach((file) => formData.append('files', file));
      const response = await fetch('/api/brief', { method: 'POST', body: formData });
      const payload = await response.json() as { ok?: boolean; error?: string };
      if (!response.ok || !payload.ok) throw new Error(payload.error || 'The message could not be sent.');
      setDraft(emptyBriefDraft);
      setFiles([]);
      setFileError('');
      setStep(1);
      setContactMethod('telegram');
      window.sessionStorage.removeItem('refraction-brief-draft');
      setStatus('success');
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : 'The message could not be sent.');
      setStatus('error');
    }
  };

  return (
    <div className="brief" role="dialog" aria-modal="true" aria-labelledby="brief-title" ref={dialogRef} tabIndex={-1}>
      <header className="brief-header">
        <a className="brand" href="#top" onClick={(event) => { event.preventDefault(); requestClose(); }} aria-label="Refraction LAB home">
          <Image src="/logo.svg" width={31} height={27} alt="" />
          <span>REFRACTION</span><i>/</i><span>LAB</span>
        </a>
        <div className="brief-header-actions">
          {hasDraft && status !== 'success' && <button className="brief-reset" type="button" onClick={clearDraft}>Clear draft</button>}
          <button className="brief-close" type="button" onClick={requestClose} aria-label="Close brief">Close <span>×</span></button>
        </div>
      </header>

      {status === 'success' ? (
        <div className="brief-success">
          <p className="section-label">Received / 00:00</p>
          <h2 id="brief-title">Your message is with the lab.</h2>
          <p>We will examine the material and reply today. There is no automated result—the response will come from the team.</p>
          <button className="button button-light" type="button" onClick={requestClose}>Return to the website <span>↘</span></button>
        </div>
      ) : (
        <form className="brief-form" ref={formRef} onSubmit={submit}>
          <input className="honeypot" type="text" name="companyWebsite" tabIndex={-1} autoComplete="off" aria-hidden="true" />
          <div className="brief-progress-row">
            <div className="brief-progress" aria-label={`Step ${step} of 3`}>
              {[1, 2, 3].map((item) => <span className={item <= step ? 'active' : ''} key={item} />)}
            </div>
            <span className="brief-step-count">0{step} / 03</span>
          </div>

          {step === 1 && (
            <fieldset>
              <legend className="section-label">01 / The situation</legend>
              <h2 id="brief-title">What is happening with your product?</h2>
              <p className="brief-copy">You do not need to structure the request or choose a service. Describe it as it is.</p>
              <label className="field-label" htmlFor="message">Your message</label>
              <textarea ref={messageRef} id="message" name="message" minLength={12} maxLength={5000} value={draft.message} onChange={(event) => updateDraft('message', event.target.value)} placeholder="The product exists, but…" required autoFocus />
              <div className="prompt-list" aria-label="Optional prompts">
                {briefPrompts.map(([label, prompt]) => <button type="button" onClick={() => applyPrompt(prompt)} key={label}>{label}<span>+</span></button>)}
              </div>
              <button className="button button-light" type="button" onClick={() => {
                if (messageRef.current?.reportValidity()) setStep(2);
              }}>Continue <span>→</span></button>
            </fieldset>
          )}

          {step === 2 && (
            <fieldset>
              <legend className="section-label">02 / The material</legend>
              <h2 id="brief-title">Show us what we can examine.</h2>
              <p className="brief-copy">Add anything that can help us understand the situation. These fields are optional.</p>
              <div className="field-grid">
                <label className="field-block" htmlFor="productLink"><span className="field-label">Product or company link</span><input id="productLink" name="productLink" type="url" value={draft.productLink} onChange={(event) => updateDraft('productLink', event.target.value)} placeholder="https://" /></label>
                <label className="field-block upload-field" htmlFor="files"><span className="field-label">Files or media</span><input id="files" name="files" type="file" multiple onChange={addFiles} aria-describedby="upload-summary" /><span className="upload-note">Up to 6 files · 10 MB each · 30 MB total</span></label>
              </div>
              <div className="upload-summary" id="upload-summary" aria-live="polite">
                <span>{files.length ? `${files.length} of ${MAX_BRIEF_FILES} files · ${formatFileSize(files.reduce((sum, file) => sum + file.size, 0))} total` : 'No files selected'}</span>
              </div>
              {files.length > 0 && <ul className="file-list">{files.map((file) => <li key={`${file.name}-${file.size}-${file.lastModified}`}><span><strong>{file.name}</strong><small>{formatFileSize(file.size)}</small></span><button type="button" onClick={() => removeFile(file)} aria-label={`Remove ${file.name}`}>Remove ×</button></li>)}</ul>}
              {fileError && <p className="form-error" role="alert">{fileError}</p>}
              <label className="no-product"><input type="checkbox" name="noProduct" value="true" checked={draft.noProduct} onChange={(event) => updateDraft('noProduct', event.target.checked)} /> There is no product yet.</label>
              <div className="brief-actions"><button className="back-button" type="button" onClick={() => setStep(1)}>← Back</button><button className="button button-light" type="button" onClick={() => setStep(3)}>Continue <span>→</span></button></div>
            </fieldset>
          )}

          {step === 3 && (
            <fieldset>
              <legend className="section-label">03 / The reply</legend>
              <h2 id="brief-title">Where should we reply?</h2>
              <p className="brief-copy">Choose the channel that is easiest for you. We reply in writing.</p>
              <div className="contact-switch" role="group" aria-label="Contact method">
                <button className={contactMethod === 'telegram' ? 'active' : ''} type="button" aria-pressed={contactMethod === 'telegram'} onClick={() => setContactMethod('telegram')}>Telegram</button>
                <button className={contactMethod === 'email' ? 'active' : ''} type="button" aria-pressed={contactMethod === 'email'} onClick={() => setContactMethod('email')}>Email</button>
              </div>
              <input type="hidden" name="contactMethod" value={contactMethod} />
              <div className="field-grid">
                <label className="field-block" htmlFor="name"><span className="field-label">Name · optional</span><input id="name" name="name" type="text" maxLength={120} value={draft.name} onChange={(event) => updateDraft('name', event.target.value)} placeholder="Your name" /></label>
                <label className="field-block" htmlFor="contact"><span className="field-label">{contactMethod === 'telegram' ? 'Telegram username' : 'Email address'}</span><input id="contact" name="contact" type={contactMethod === 'email' ? 'email' : 'text'} maxLength={180} value={draft[contactMethod]} onChange={(event) => updateDraft(contactMethod, event.target.value)} placeholder={contactMethod === 'telegram' ? '@username' : 'name@company.com'} required /></label>
              </div>
              <label className="consent"><input type="checkbox" name="consent" value="true" checked={draft.consent} onChange={(event) => updateDraft('consent', event.target.checked)} required /> I agree that Refraction LAB may use the submitted information to review and reply to this request.</label>
              {error && <p className="form-error" role="alert">{error}</p>}
              <div className="brief-actions"><button className="back-button" type="button" onClick={() => setStep(2)}>← Back</button><button className="button button-light" type="submit" disabled={status === 'sending'}>{status === 'sending' ? 'Sending…' : 'Send to the lab'} <span>↗</span></button></div>
            </fieldset>
          )}
        </form>
      )}
    </div>
  );
}

export default function Home() {
  const [briefOpen, setBriefOpen] = useState(false);
  const [expandedCapability, setExpandedCapability] = useState<number | null>(null);
  const [expandedRoute, setExpandedRoute] = useState<'proven' | 'lab' | null>(null);
  const openBrief = useCallback(() => setBriefOpen(true), []);
  const closeBrief = useCallback(() => setBriefOpen(false), []);

  useEffect(() => {
    const elements = document.querySelectorAll<HTMLElement>('[data-reveal]');
    const readyTimers: number[] = [];
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      elements.forEach((element) => {
        element.dataset.visible = 'true';
        element.dataset.motionReady = 'true';
      });
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const element = entry.target as HTMLElement;
          element.dataset.visible = 'true';
          readyTimers.push(window.setTimeout(() => {
            element.dataset.motionReady = 'true';
          }, 1180));
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.13 });
    elements.forEach((element) => observer.observe(element));
    return () => {
      observer.disconnect();
      readyTimers.forEach((timer) => window.clearTimeout(timer));
    };
  }, []);

  return (
    <main>
      <SiteHeader onOpenBrief={openBrief} />
      <section className="hero" id="top" data-nav-section>

        <RefractionCanvas />
        <div className="hero-logo" data-hero-prism aria-hidden="true"><Image src="/logo.svg" width={524} height={455} alt="" priority /></div>
        <div className="hero-content shell">
          <p className="eyebrow">Independent digital product laboratory</p>
          <h1>There is no universal solution to a product problem.</h1>
          <p className="hero-copy">Tell us what is happening. We examine the product, identify the real cause and define a way forward—from analysis to implementation.</p>
          <div className="hero-actions">
            <button className="button button-light" type="button" onClick={openBrief}>Bring us the problem <span>↗</span></button>
            <a className="text-link" href="#approach">See how we work <span>↓</span></a>
          </div>
          <p className="microcopy">Text, links, files or media. We reply the same day.</p>
        </div>
        <div className="hero-index" aria-hidden="true"><span>01</span><span>UNKNOWN</span><span>REFRACTION</span><span>CLARITY</span></div>
      </section>

      <section className="refraction-band" data-reveal aria-label="From one visible problem to multiple possible causes">
        <span data-motion="label">One visible problem</span><div className="spectrum" data-motion="flow" /><span data-motion="label">Multiple possible causes</span>
      </section>

      <OpticalNarrative />

      <section className="diagnosis light-section full-section" id="approach" data-optical-state="diagnosis" data-optical-theme="light">
        <div className="shell" data-reveal>
          <div className="section-heading"><p className="section-label" data-motion="label">01 / Diagnosis</p><h2 data-motion="heading">The symptom is not always the cause.</h2></div>
          <p className="section-intro" data-motion="copy">A redesign, more traffic or new technology may be part of the answer. First, we determine what is actually preventing the product from working.</p>
          <div className="contrast-list">
            {[
              ['“We need a new design.”', 'The offer may be unclear, or the user journey has no decisive moment.'],
              ['“We need more traffic.”', 'The product may lose people before they reach the action that matters.'],
              ['“Our website is outdated.”', 'The business may have outgrown the system behind it.'],
              ['“We need an app.”', 'First, we validate what the app must change for the business and its users.'],
            ].map(([symptom, cause], index) => <article className="contrast-row" data-motion="item" data-ray-target data-ray-anchor="bottom-right" key={symptom}><span className="row-index">0{index + 1}</span><h3>{symptom}</h3><p>{cause}</p></article>)}
          </div>
          <p className="large-statement" data-motion="statement">We do not prescribe before we understand.</p>
          <button className="section-cta" data-motion="action" type="button" onClick={openBrief}>Show us the symptom <span>↗</span></button>
        </div>
      </section>

      <section className="situations paper-section full-section" id="situations" data-optical-state="situations" data-optical-theme="light">
        <div className="shell" data-reveal>
          <div className="section-heading"><p className="section-label" data-motion="label">02 / Any stage</p><h2 data-motion="heading">Bring the idea, the product or the problem.</h2></div>
          <p className="section-intro" data-motion="copy">You do not need to translate the situation into a service brief. Describe it as it is. We will structure the task.</p>
          <div className="situation-grid">
            {situations.map(([title, copy], index) => <article className="situation-item" data-motion="item" data-ray-target data-ray-anchor="top-left" key={title}><span className="row-index">0{index + 1}</span><h3>{title}</h3><p>{copy}</p></article>)}
          </div>
          <p className="quiet-statement" data-motion="statement">If it belongs to a digital product, it belongs in the conversation.</p>
        </div>
      </section>

      <section className="process light-section full-section" id="process" data-optical-state="process" data-optical-theme="light">
        <div className="shell" data-reveal>
          <div className="section-heading"><p className="section-label" data-motion="label">03 / What happens next</p><h2 data-motion="heading">We start working before we start selling.</h2></div>
          <p className="section-intro" data-motion="copy">Send the context, a link and any useful files. We review the material and reply the same day with our first observations.</p>
          <ol className="process-list">
            {process.map(([title, copy], index) => <li data-motion="item" data-ray-target data-ray-anchor="bottom-right" key={title}><span className="row-index">0{index + 1}</span><h3>{title}</h3><p>{copy}</p></li>)}
          </ol>
          <div className="process-close">
            <p className="process-note" data-motion="statement">No automated report. No prewritten diagnosis. A response from the team.</p>
            <button className="section-cta compact" data-motion="action" type="button" onClick={openBrief}>Send us the context <span>↗</span></button>
          </div>
        </div>
      </section>

      <section className="audit dark-section full-section" id="audit" data-optical-state="audit" data-optical-theme="dark">
        <div className="shell" data-reveal>
          <div className="section-heading"><p className="section-label" data-motion="label">04 / Audit</p><h2 data-motion="heading">Not a list of faults. A working model.</h2></div>
          <div className="audit-layout">
            <p className="audit-copy" data-motion="copy">The audit connects product logic, user experience, technology, brand and marketing. It explains not only what is wrong, but what can be done next.</p>
            <ul className="audit-list"><li data-motion="item" data-ray-target data-ray-anchor="top-left">Current state</li><li data-motion="item" data-ray-target data-ray-anchor="top-left">Visible and hidden problems</li><li data-motion="item" data-ray-target data-ray-anchor="top-left">Possible causes</li><li data-motion="item" data-ray-target data-ray-anchor="top-left">Dependencies</li><li data-motion="item" data-ray-target data-ray-anchor="top-left">Alternative solution routes</li><li data-motion="item" data-ray-target data-ray-anchor="top-left">Recommended next move</li></ul>
          </div>
          <div className="model-flow" data-motion="flow" aria-label="Audit flow"><span>Current state</span><i>→</i><span>Causes</span><i>→</i><span>Models</span><i>→</i><span>Route</span></div>
          <p className="large-statement light" data-motion="statement">A problem description becomes a decision the business can act on.</p>
        </div>
      </section>

      <section className="method paper-section full-section" id="method" data-optical-state="method" data-optical-theme="light">
        <div className="shell" data-reveal>
          <div className="section-heading"><p className="section-label" data-motion="label">05 / Method</p><h2 data-motion="heading">One task. Six states.</h2></div>
          <p className="section-intro" data-motion="copy">Each state reduces uncertainty before the next investment is made.</p>
          <ol className="method-list">
            {method.map(([title, copy, state], index) => <li data-motion="item" data-ray-target data-ray-anchor="bottom-right" key={title}><span className="method-number">{String(index + 1).padStart(2, '0')}</span><div><h3>{title}</h3><p>{copy}</p></div><span className="method-state">{state}</span></li>)}
          </ol>
        </div>
      </section>

      <section className="capabilities light-section full-section" id="capabilities" data-optical-state="capabilities" data-optical-theme="light">
        <div className="shell" data-reveal>
          <div className="section-heading"><p className="section-label" data-motion="label">06 / Implementation</p><h2 data-motion="heading">From model to working product.</h2></div>
          <p className="section-intro" data-motion="copy">We do not sell a predefined service. We combine the disciplines required by the task.</p>
          <div className="capability-list">
            {capabilities.map(([title, copy, detail, points], index) => {
              const open = expandedCapability === index;
              return (
                <article className={open ? 'is-open' : ''} data-motion="item" data-ray-target data-ray-anchor="top-left" key={title}>
                  <button className="capability-trigger" type="button" aria-expanded={open} aria-controls={`capability-${index}`} onClick={() => setExpandedCapability(open ? null : index)}>
                    <span className="row-index">0{index + 1}</span><h3>{title}</h3><p>{copy}</p><span className="capability-arrow" aria-hidden="true">{open ? '−' : '+'}</span>
                  </button>
                  <div className="capability-detail" id={`capability-${index}`} aria-hidden={!open}>
                    <div><p>{detail}</p><ul>{points.map((point) => <li key={point}>{point}</li>)}</ul></div>
                  </div>
                </article>
              );
            })}
          </div>
          <div className="capabilities-close">
            <button className="section-cta" data-motion="action" type="button" onClick={openBrief}>Bring us the task <span>↗</span></button>
            <p className="quiet-statement" data-motion="statement">The solution defines the team—not the other way around.</p>
          </div>
        </div>
      </section>

      <section className="experiments paper-section full-section" id="experiments" data-optical-state="experiments" data-optical-theme="light">
        <div className="shell" data-reveal>
          <div className="section-heading"><p className="section-label" data-motion="label">07 / Experiments</p><h2 data-motion="heading">As experimental as the task needs.</h2></div>
          <div className="route-grid">
            <article className={`route-card ${expandedRoute === 'proven' ? 'is-open' : ''}`} data-motion="item">
              <button className="route-trigger" type="button" aria-expanded={expandedRoute === 'proven'} aria-controls="proven-route" onClick={() => setExpandedRoute(expandedRoute === 'proven' ? null : 'proven')}>
                <div className="route-visual stable" data-ray-target data-ray-anchor="bottom-right" aria-hidden="true"><span /><span /><span /></div><p className="section-label">Proven route</p><h3>When certainty matters.</h3><p>Established patterns, reliable technology and controlled implementation for tasks where predictability is the priority.</p><span className="route-toggle">Explore the route <b>{expandedRoute === 'proven' ? '−' : '+'}</b></span>
              </button>
              <div className="route-detail" id="proven-route" aria-hidden={expandedRoute !== 'proven'}><div><p>Best for known tasks where delivery confidence matters more than novelty.</p><ul><li>Established interaction patterns</li><li>Controlled scope and implementation</li><li>Validation focused on fit and execution</li></ul></div></div>
            </article>
            <article className={`route-card lab-route ${expandedRoute === 'lab' ? 'is-open' : ''}`} data-motion="item">
              <button className="route-trigger" type="button" aria-expanded={expandedRoute === 'lab'} aria-controls="lab-route" onClick={() => setExpandedRoute(expandedRoute === 'lab' ? null : 'lab')}>
                <div className="route-visual spectrum-route" data-ray-target data-ray-anchor="top-left" aria-hidden="true"><span /><span /><span /></div><p className="section-label">LAB route</p><h3>When advantage matters.</h3><p>New mechanics, interfaces, technologies and product hypotheses for tasks where a conventional solution is not enough.</p><span className="route-toggle">Explore the route <b>{expandedRoute === 'lab' ? '−' : '+'}</b></span>
              </button>
              <div className="route-detail" id="lab-route" aria-hidden={expandedRoute !== 'lab'}><div><p>Best when the advantage depends on an assumption that should be tested before full investment.</p><ul><li>One critical hypothesis at a time</li><li>Controlled prototype or experiment</li><li>Evidence before full implementation</li></ul></div></div>
            </article>
          </div>
          <p className="experiment-principle" data-motion="statement">We test unconventional ideas at a controlled scale before turning them into a full product.</p>
        </div>
      </section>

      <section className="final-cta dark-section" id="contact" data-optical-state="convergence" data-optical-theme="dark">
        <div className="final-glow" aria-hidden="true" />
        <div className="final-logo" aria-hidden="true"><Image src="/logo.svg" width={524} height={455} alt="" /></div>
        <div className="shell" data-reveal>
          <p className="section-label" data-motion="label">Start with the problem</p>
          <h2 data-motion="heading">You do not need to know what service you need.</h2>
          <p data-motion="copy">Tell us what is happening. Add a link, files or media if they help. We will examine the material and reply today.</p>
          <button className="button button-light" data-motion="action" data-ray-target data-ray-anchor="top-right" type="button" onClick={openBrief}>Bring us the problem <span>↗</span></button>
          <span className="final-note" data-motion="statement">No automated report. Just the beginning of an informed conversation.</span>
        </div>
      </section>

      <footer className="footer dark-section">
        <div className="shell footer-grid" data-reveal>
          <a className="brand" data-motion="item" href="#top"><Image src="/logo.svg" width={31} height={27} alt="" /><span>REFRACTION</span><i>/</i><span>LAB</span></a>
          <div data-motion="item"><span>Independent digital</span><span>product laboratory</span></div>
          <div data-motion="item"><button type="button" onClick={openBrief}>Telegram / Email ↗</button><a href="#approach">Approach</a><a href="#capabilities">Capabilities</a></div>
          <div data-motion="item"><span>English</span><span>ES / CA coming next</span><span>© {new Date().getFullYear()}</span></div>
        </div>
      </footer>

      <BriefModal open={briefOpen} onClose={closeBrief} />
    </main>
  );
}
