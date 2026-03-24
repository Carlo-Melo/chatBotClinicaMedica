create extension if not exists pgcrypto;

create table if not exists patients (
    id uuid primary key default gen_random_uuid(),
    phone text not null unique,
    name text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists conversation_history (
    id bigint generated always as identity primary key,
    phone text not null,
    sender text not null,
    message text not null,
    message_type text not null default 'text',
    metadata jsonb not null default '{}'::jsonb,
    timestamp timestamptz not null default timezone('utc', now())
);

create index if not exists idx_conversation_history_phone_timestamp
    on conversation_history (phone, timestamp desc);

create table if not exists appointment_requests (
    id uuid primary key default gen_random_uuid(),
    patient_id uuid references patients(id) on delete set null,
    patient_name text,
    phone text not null,
    doctor text not null,
    requested_date text not null,
    requested_date_iso timestamptz,
    notes text,
    status text not null default 'PENDING',
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now())
);
