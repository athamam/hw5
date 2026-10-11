import type { AgentName } from './api'

export interface AgentMeta {
  name: AgentName
  label: string
  nickname: string
  role: string
  color: string
  accessory: 'crown' | 'box' | 'glasses' | 'hardhat' | 'headset'
}

// Each agent has its own colour, accessory and voice so they read differently at a glance.
export const AGENTS: Record<AgentName, AgentMeta> = {
  boss: {
    name: 'boss',
    label: 'Boss',
    nickname: 'Big Bun',
    role: 'Reads the ticket, picks the crew, makes the call',
    color: '#d6336c',
    accessory: 'crown',
  },
  inventory: {
    name: 'inventory',
    label: 'Inventory',
    nickname: 'Shelfie',
    role: 'Counts stock by SKU and size, finds who can restock',
    color: '#ff6f91',
    accessory: 'box',
  },
  accounting: {
    name: 'accounting',
    label: 'Accounting',
    nickname: 'Penny',
    role: 'Watches cash and margins, preps pay and POs',
    color: '#b05fd6',
    accessory: 'glasses',
  },
  facilities: {
    name: 'facilities',
    label: 'Facilities',
    nickname: 'Keys',
    role: 'Leases, rent and the shop space',
    color: '#ff8c69',
    accessory: 'hardhat',
  },
  customer_service: {
    name: 'customer_service',
    label: 'Customer Service',
    nickname: 'Hello Kit',
    role: 'Drafts friendly notes (never sends them)',
    color: '#e05cc0',
    accessory: 'headset',
  },
}

export const AGENT_ORDER: AgentName[] = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service']

// What an agent is "doing" when it calls each MCP tool, in plain words.
export const TOOL_VERBS: Record<string, string> = {
  get_desk: 'Checking today’s date',
  list_tickets: 'Scanning the board',
  get_ticket: 'Reading the ticket',
  check_stock: 'Counting the shelves',
  get_pricing: 'Checking cost and margin',
  list_vendors: 'Flipping through vendors',
  check_vendor_can_ship: 'Asking if the vendor can ship',
  list_invoices: 'Digging through invoices',
  get_lease: 'Pulling out the lease',
  get_cash_balance: 'Peeking at the piggy bank',
  list_approvals: 'Checking the approval tray',
  add_ticket_note: 'Pinning a note to the ticket',
  update_ticket_status: 'Updating the ticket status',
  request_payment: 'Preparing a payment slip',
  create_purchase_order: 'Drafting a purchase order',
  propose_price_override: 'Pencilling in a discount',
  draft_customer_message: 'Writing a draft message',
  delegate: 'Handing off work',
}

export const TICKET_ICONS: Record<string, string> = {
  customer_order: '👕',
  rent_notice: '🏠',
  price_override: '🏷️',
}

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })
