'use client';

import Image from 'next/image';
import { FormEvent, useEffect, useRef, useState } from 'react';

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
  ['Observe', 'Business, product, users, data and constraints.'],
  ['Refract', 'Commercial, product, visual and technical components.'],
  ['Model', 'Structures, scenarios, prototypes and solution routes.'],
  ['Experiment', 'Critical assumptions tested before full implementation.'],
  ['Build', 'Design, development, integration and launch.'],
  ['Evolve', 'Support, observation and continuous improvement.'],
];

const capabilities = [
  ['Product', 'Research, product logic, business models and validation.'],
  ['Web', 'Marketing sites, platforms, services and interactive experiences.'],
  ['Mobile', 'Product concepts, interfaces, applications and supporting systems.'],
  ['Brand', 'Positioning, identity, offers and communication systems.'],
  ['Marketing', 'Acquisition models, campaigns, content and analytics.'],
  ['Technology', 'Frontend, backend, integrations and technical support.'],
];

function RefractionCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext('2d');
    if (!context) return;
    let pointerX = 0.7;
    let pointerY = 0.47;
    let scheduled = 0;

    const draw = () => {
      scheduled = 0;
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
        canvas.width = Math.round(width * ratio);
        canvas.height = Math.round(height * ratio);
      }
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, width, height);

      const originX = width * 0.035;
      const originY = height * pointerY;
      const prismX = width * 0.67;
      const prismY = height * 0.43;
      const drift = (pointerX - 0.5) * 52;

      context.lineCap = 'round';
      context.globalCompositeOperation = 'lighter';
      context.strokeStyle = 'rgba(255,255,255,.7)';
      context.lineWidth = 1;
      context.beginPath();
      context.moveTo(originX, originY);
      context.lineTo(prismX, prismY);
      context.stroke();

      const rays = [
        ['rgba(83,197,255,.68)', -0.23],
        ['rgba(124,119,255,.64)', -0.10],
        ['rgba(213,108,255,.58)', 0.03],
        ['rgba(255,118,170,.5)', 0.16],
      ] as const;

      rays.forEach(([color, offset], index) => {
        const endY = prismY + height * offset + drift + index * 3;
        const gradient = context.createLinearGradient(prismX, prismY, width, endY);
        gradient.addColorStop(0, color);
        gradient.addColorStop(1, color.replace(/\.[0-9]+\)/, '.025)'));
        context.strokeStyle = gradient;
        context.lineWidth = 1.1 + index * 0.22;
        context.beginPath();
        context.moveTo(prismX, prismY);
        context.lineTo(width, endY);
        context.stroke();
      });

      const glow = context.createRadialGradient(prismX, prismY, 0, prismX, prismY, width * 0.17);
      glow.addColorStop(0, 'rgba(141,124,255,.2)');
      glow.addColorStop(1, 'rgba(5,5,6,0)');
      context.fillStyle = glow;
      context.fillRect(0, 0, width, height);
      context.globalCompositeOperation = 'source-over';
    };

    const schedule = () => {
      if (!scheduled) scheduled = requestAnimationFrame(draw);
    };
    const onPointer = (event: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      pointerX = (event.clientX - rect.left) / rect.width;
      pointerY = Math.max(0.26, Math.min(0.68, (event.clientY - rect.top) / rect.height));
      schedule();
    };

    schedule();
    window.addEventListener('resize', schedule);
    canvas.addEventListener('pointermove', onPointer);
    return () => {
      if (scheduled) cancelAnimationFrame(scheduled);
      window.removeEventListener('resize', schedule);
      canvas.removeEventListener('pointermove', onPointer);
    };
  }, []);

  return <canvas className="hero-canvas" ref={canvasRef} aria-hidden="true" />;
}

type BriefModalProps = { open: boolean; onClose: () => void };

function BriefModal({ open, onClose }: BriefModalProps) {
  const [step, setStep] = useState(1);
  const [contactMethod, setContactMethod] = useState<'telegram' | 'email'>('telegram');
  const [status, setStatus] = useState<'idle' | 'sending' | 'success' | 'error'>('idle');
  const [error, setError] = useState('');
  const dialogRef = useRef<HTMLDivElement>(null);
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    requestAnimationFrame(() => dialogRef.current?.focus());
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', onKey);
    };
  }, [open, onClose]);

  if (!open) return null;

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = formRef.current;
    if (!form) return;
    setStatus('sending');
    setError('');
    try {
      const response = await fetch('/api/brief', { method: 'POST', body: new FormData(form) });
      const payload = await response.json() as { ok?: boolean; error?: string };
      if (!response.ok || !payload.ok) throw new Error(payload.error || 'The message could not be sent.');
      setStatus('success');
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : 'The message could not be sent.');
      setStatus('error');
    }
  };

  return (
    <div className="brief" role="dialog" aria-modal="true" aria-labelledby="brief-title" ref={dialogRef} tabIndex={-1}>
      <header className="brief-header">
        <a className="brand" href="#top" onClick={onClose} aria-label="Refraction LAB home">
          <Image src="/logo.svg" width={31} height={27} alt="" />
          <span>REFRACTION</span><i>/</i><span>LAB</span>
        </a>
        <button className="brief-close" type="button" onClick={onClose} aria-label="Close brief">Close <span>×</span></button>
      </header>

      {status === 'success' ? (
        <div className="brief-success">
          <p className="section-label">Received / 00:00</p>
          <h2>Your message is with the lab.</h2>
          <p>We will examine the material and reply today. There is no automated result—the response will come from the team.</p>
          <button className="button button-light" type="button" onClick={onClose}>Return to the website <span>↘</span></button>
        </div>
      ) : (
        <form className="brief-form" ref={formRef} onSubmit={submit}>
          <input className="honeypot" type="text" name="companyWebsite" tabIndex={-1} autoComplete="off" aria-hidden="true" />
          <div className="brief-progress" aria-label={`Step ${step} of 3`}>
            {[1, 2, 3].map((item) => <span className={item <= step ? 'active' : ''} key={item} />)}
          </div>

          {step === 1 && (
            <fieldset>
              <legend className="section-label">01 / The situation</legend>
              <h2 id="brief-title">What is happening with your product?</h2>
              <p className="brief-copy">You do not need to structure the request or choose a service. Describe it as it is.</p>
              <label className="field-label" htmlFor="message">Your message</label>
              <textarea id="message" name="message" minLength={12} maxLength={5000} placeholder="The product exists, but…" required autoFocus />
              <div className="prompt-list" aria-label="Optional prompts">
                <span>We have an idea</span><span>It is not performing</span><span>It needs to be rebuilt</span><span>We are not sure</span>
              </div>
              <button className="button button-light" type="button" onClick={() => {
                const message = formRef.current?.elements.namedItem('message') as HTMLTextAreaElement | null;
                if (message?.reportValidity()) setStep(2);
              }}>Continue <span>→</span></button>
            </fieldset>
          )}

          {step === 2 && (
            <fieldset>
              <legend className="section-label">02 / The material</legend>
              <h2>Show us what we can examine.</h2>
              <p className="brief-copy">Add anything that can help us understand the situation. These fields are optional.</p>
              <div className="field-grid">
                <label className="field-block" htmlFor="productLink"><span className="field-label">Product or company link</span><input id="productLink" name="productLink" type="url" placeholder="https://" /></label>
                <label className="field-block upload-field" htmlFor="files"><span className="field-label">Files or media</span><input id="files" name="files" type="file" multiple /><span className="upload-note">Up to 6 files · 30 MB total</span></label>
              </div>
              <label className="no-product"><input type="checkbox" name="noProduct" value="true" /> There is no product yet.</label>
              <div className="brief-actions"><button className="back-button" type="button" onClick={() => setStep(1)}>← Back</button><button className="button button-light" type="button" onClick={() => setStep(3)}>Continue <span>→</span></button></div>
            </fieldset>
          )}

          {step === 3 && (
            <fieldset>
              <legend className="section-label">03 / The reply</legend>
              <h2>Where should we reply?</h2>
              <p className="brief-copy">Choose the channel that is easiest for you. We reply in writing.</p>
              <div className="contact-switch" role="group" aria-label="Contact method">
                <button className={contactMethod === 'telegram' ? 'active' : ''} type="button" onClick={() => setContactMethod('telegram')}>Telegram</button>
                <button className={contactMethod === 'email' ? 'active' : ''} type="button" onClick={() => setContactMethod('email')}>Email</button>
              </div>
              <input type="hidden" name="contactMethod" value={contactMethod} />
              <div className="field-grid">
                <label className="field-block" htmlFor="name"><span className="field-label">Name · optional</span><input id="name" name="name" type="text" maxLength={120} placeholder="Your name" /></label>
                <label className="field-block" htmlFor="contact"><span className="field-label">{contactMethod === 'telegram' ? 'Telegram username' : 'Email address'}</span><input id="contact" name="contact" type={contactMethod === 'email' ? 'email' : 'text'} maxLength={180} placeholder={contactMethod === 'telegram' ? '@username' : 'name@company.com'} required /></label>
              </div>
              <label className="consent"><input type="checkbox" name="consent" value="true" required /> I agree that Refraction LAB may use the submitted information to review and reply to this request.</label>
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
  const openBrief = () => setBriefOpen(true);

  useEffect(() => {
    const elements = document.querySelectorAll<HTMLElement>('[data-reveal]');
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      elements.forEach((element) => element.dataset.visible = 'true');
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          (entry.target as HTMLElement).dataset.visible = 'true';
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.13 });
    elements.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, []);

  return (
    <main>
      <section className="hero" id="top">
        <nav className="nav shell" aria-label="Main navigation">
          <a className="brand" href="#top" aria-label="Refraction LAB home">
            <Image src="/logo.svg" width={31} height={27} alt="" priority />
            <span>REFRACTION</span><i>/</i><span>LAB</span>
          </a>
          <div className="nav-links">
            <a href="#approach">Approach</a>
            <a href="#capabilities">Capabilities</a>
            <a href="#experiments">Experiments</a>
            <button className="nav-cta" type="button" onClick={openBrief}>Contact</button>
          </div>
        </nav>

        <RefractionCanvas />
        <div className="hero-logo" aria-hidden="true"><Image src="/logo.svg" width={524} height={455} alt="" priority /></div>
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

      <section className="refraction-band" aria-label="From one visible problem to multiple possible causes">
        <span>One visible problem</span><div className="spectrum" /><span>Multiple possible causes</span>
      </section>

      <section className="diagnosis light-section full-section" id="approach">
        <div className="shell" data-reveal>
          <div className="section-heading"><p className="section-label">01 / Diagnosis</p><h2>The symptom is not always the cause.</h2></div>
          <p className="section-intro">A redesign, more traffic or new technology may be part of the answer. First, we determine what is actually preventing the product from working.</p>
          <div className="contrast-list">
            {[
              ['“We need a new design.”', 'The offer may be unclear, or the user journey has no decisive moment.'],
              ['“We need more traffic.”', 'The product may lose people before they reach the action that matters.'],
              ['“Our website is outdated.”', 'The business may have outgrown the system behind it.'],
              ['“We need an app.”', 'First, we validate what the app must change for the business and its users.'],
            ].map(([symptom, cause], index) => <article className="contrast-row" key={symptom}><span className="row-index">0{index + 1}</span><h3>{symptom}</h3><p>{cause}</p></article>)}
          </div>
          <p className="large-statement">We do not prescribe before we understand.</p>
        </div>
      </section>

      <section className="situations paper-section full-section">
        <div className="shell" data-reveal>
          <div className="section-heading"><p className="section-label">02 / Any stage</p><h2>Bring the idea, the product or the problem.</h2></div>
          <p className="section-intro">You do not need to translate the situation into a service brief. Describe it as it is. We will structure the task.</p>
          <div className="situation-grid">
            {situations.map(([title, copy], index) => <article className="situation-item" key={title}><span className="row-index">0{index + 1}</span><h3>{title}</h3><p>{copy}</p></article>)}
          </div>
          <p className="quiet-statement">If it belongs to a digital product, it belongs in the conversation.</p>
        </div>
      </section>

      <section className="process light-section full-section">
        <div className="shell" data-reveal>
          <div className="section-heading"><p className="section-label">03 / What happens next</p><h2>We start working before we start selling.</h2></div>
          <p className="section-intro">Send the context, a link and any useful files. We review the material and reply the same day with our first observations.</p>
          <ol className="process-list">
            {process.map(([title, copy], index) => <li key={title}><span className="row-index">0{index + 1}</span><h3>{title}</h3><p>{copy}</p></li>)}
          </ol>
          <p className="process-note">No automated report. No prewritten diagnosis. A response from the team.</p>
        </div>
      </section>

      <section className="audit dark-section full-section">
        <div className="shell" data-reveal>
          <div className="section-heading"><p className="section-label">04 / Audit</p><h2>Not a list of faults. A working model.</h2></div>
          <div className="audit-layout">
            <p className="audit-copy">The audit connects product logic, user experience, technology, brand and marketing. It explains not only what is wrong, but what can be done next.</p>
            <ul className="audit-list"><li>Current state</li><li>Visible and hidden problems</li><li>Possible causes</li><li>Dependencies</li><li>Alternative solution routes</li><li>Recommended next move</li></ul>
          </div>
          <div className="model-flow" aria-label="Audit flow"><span>Current state</span><i>→</i><span>Causes</span><i>→</i><span>Models</span><i>→</i><span>Route</span></div>
          <p className="large-statement light">A problem description becomes a decision the business can act on.</p>
        </div>
      </section>

      <section className="method paper-section full-section">
        <div className="shell" data-reveal>
          <div className="section-heading"><p className="section-label">05 / Method</p><h2>One task. Six states.</h2></div>
          <p className="section-intro">Each state reduces uncertainty before the next investment is made.</p>
          <ol className="method-list">
            {method.map(([title, copy], index) => <li key={title}><span className="method-number">{String(index + 1).padStart(2, '0')}</span><div><h3>{title}</h3><p>{copy}</p></div></li>)}
          </ol>
        </div>
      </section>

      <section className="capabilities light-section full-section" id="capabilities">
        <div className="shell" data-reveal>
          <div className="section-heading"><p className="section-label">06 / Implementation</p><h2>From model to working product.</h2></div>
          <p className="section-intro">We do not sell a predefined service. We combine the disciplines required by the task.</p>
          <div className="capability-list">
            {capabilities.map(([title, copy], index) => <article key={title}><span className="row-index">0{index + 1}</span><h3>{title}</h3><p>{copy}</p><span className="capability-arrow">↗</span></article>)}
          </div>
          <p className="quiet-statement">The solution defines the team—not the other way around.</p>
        </div>
      </section>

      <section className="experiments paper-section full-section" id="experiments">
        <div className="shell" data-reveal>
          <div className="section-heading"><p className="section-label">07 / Experiments</p><h2>As experimental as the task needs.</h2></div>
          <div className="route-grid">
            <article className="route-card"><div className="route-visual stable" aria-hidden="true"><span /><span /><span /></div><p className="section-label">Proven route</p><h3>When certainty matters.</h3><p>Established patterns, reliable technology and controlled implementation for tasks where predictability is the priority.</p></article>
            <article className="route-card lab-route"><div className="route-visual spectrum-route" aria-hidden="true"><span /><span /><span /></div><p className="section-label">LAB route</p><h3>When advantage matters.</h3><p>New mechanics, interfaces, technologies and product hypotheses for tasks where a conventional solution is not enough.</p></article>
          </div>
          <p className="experiment-principle">We test unconventional ideas at a controlled scale before turning them into a full product.</p>
        </div>
      </section>

      <section className="final-cta dark-section">
        <div className="final-glow" aria-hidden="true" />
        <div className="shell" data-reveal>
          <p className="section-label">Start with the problem</p>
          <h2>You do not need to know what service you need.</h2>
          <p>Tell us what is happening. Add a link, files or media if they help. We will examine the material and reply today.</p>
          <button className="button button-light" type="button" onClick={openBrief}>Bring us the problem <span>↗</span></button>
          <span className="final-note">No automated report. Just the beginning of an informed conversation.</span>
        </div>
      </section>

      <footer className="footer dark-section">
        <div className="shell footer-grid">
          <a className="brand" href="#top"><Image src="/logo.svg" width={31} height={27} alt="" /><span>REFRACTION</span><i>/</i><span>LAB</span></a>
          <div><span>Independent digital</span><span>product laboratory</span></div>
          <div><button type="button" onClick={openBrief}>Telegram / Email ↗</button><a href="#approach">Approach</a><a href="#capabilities">Capabilities</a></div>
          <div><span>English</span><span>ES / CA coming next</span><span>© {new Date().getFullYear()}</span></div>
        </div>
      </footer>

      <BriefModal open={briefOpen} onClose={() => setBriefOpen(false)} />
    </main>
  );
}
