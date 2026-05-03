export interface PartyIntake {
  name: string;
  address: string;
  city: string;
  state: string;
  zip_code: string;
  phone: string;
  email: string;
}

export interface DefendantIntake extends PartyIntake {
  dos_entity_name?: string;
  dos_id?: string;
  service_address?: string;
  registered_agent?: string;
}

export interface ContractIntake {
  date_formed?: string;          // ISO YYYY-MM-DD
  scope_of_work: string;
  agreed_amount: number;
  payment_terms?: string;
}

export interface PerformanceIntake {
  delivered_on?: string;
  deliverables?: string[];
}

export interface BreachIntake {
  date?: string;
  nature: string;
  amount_owed: number;
}

export interface VenueIntake {
  borough: '' | 'Manhattan' | 'Bronx' | 'Brooklyn' | 'Queens' | 'Staten Island';
  basis: string;
}

export interface IntakeForm {
  plaintiff: PartyIntake;
  defendant: DefendantIntake;
  contract: ContractIntake;
  performance: PerformanceIntake;
  breach: BreachIntake;
  venue: VenueIntake;
  evidence?: Array<{ filename: string; mime_type: string; text: string }>;
}

export const emptyIntake = (): IntakeForm => ({
  plaintiff: { name: '', address: '', city: '', state: 'NY', zip_code: '', phone: '', email: '' },
  defendant: { name: '', address: '', city: '', state: 'NY', zip_code: '', phone: '', email: '' },
  contract: { date_formed: '', scope_of_work: '', agreed_amount: 0, payment_terms: '' },
  performance: { delivered_on: '', deliverables: [] },
  breach: { date: '', nature: 'non-payment', amount_owed: 0 },
  venue: { borough: '', basis: '' },
});

export const demoIntake: IntakeForm = {
  plaintiff: {
    name: 'Jane Q. Doe',
    address: '123 Smith Street',
    city: 'Brooklyn',
    state: 'NY',
    zip_code: '11201',
    phone: '(718) 555-0100',
    email: 'jane@janedoedesign.example',
  },
  defendant: {
    name: 'Vanguard Marketing LLC',
    address: '',
    city: '',
    state: 'NY',
    zip_code: '',
    phone: '',
    email: '',
  },
  contract: {
    date_formed: '2025-01-15',
    scope_of_work:
      "Twelve (12) original illustrations and a one-page brand-color guideline for Vanguard Marketing LLC's Spring 2025 product launch, delivered as print-ready PDF + editable AI files.",
    agreed_amount: 4800.0,
    payment_terms: 'Net 30 from delivery.',
  },
  performance: {
    delivered_on: '2025-03-01',
    deliverables: ['12 illustrations (PDF + AI)', '1 brand-color guideline (PDF)'],
  },
  breach: {
    date: '2025-03-31',
    nature: 'non-payment',
    amount_owed: 4800.0,
  },
  venue: {
    borough: 'Brooklyn',
    basis: "Defendant's principal place of business is in Brooklyn, and the parties' agreement was performed there.",
  },
};

/** Wire-format event coming over the WebSocket from the backend.
 *  Mirrors the discriminated union in backend/events.py.
 */
export interface AgentEvent {
  type: string;
  name?: string;
  agent?: string;
  from_agent?: string;
  to_agent?: string;
  tool_name?: string;
  args?: any;
  preview?: string;
  preview_truncated?: boolean;
  facts?: any;
  pdf_ready?: boolean;
  message?: string;
  attempt?: number;
  reason?: string;
}
