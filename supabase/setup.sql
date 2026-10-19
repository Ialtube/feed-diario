-- El Rincón del Feeder: comentarios y noticias propuestas por los lectores.
-- Pégalo entero en Supabase → SQL Editor → New query → Run. Se puede ejecutar más de una vez.

-- ---------------------------------------------------------------- comentarios
create table if not exists public.comentarios (
  id bigint generated always as identity primary key,
  edicion date not null,
  nombre text not null check (char_length(nombre) between 1 and 40),
  texto text not null check (char_length(texto) between 1 and 1000),
  created_at timestamptz not null default now()
);
alter table public.comentarios enable row level security;
drop policy if exists "leer comentarios" on public.comentarios;
create policy "leer comentarios" on public.comentarios for select to anon using (true);
drop policy if exists "escribir comentarios" on public.comentarios;
create policy "escribir comentarios" on public.comentarios for insert to anon with check (true);

-- ---------------------------------------------------------------- noticias propuestas
create table if not exists public.propuestas (
  id bigint generated always as identity primary key,
  nombre text not null check (char_length(nombre) between 1 and 40),
  titulo text not null check (char_length(titulo) between 3 and 140),
  texto text not null check (char_length(texto) between 10 and 2000),
  imagen text check (imagen is null or char_length(imagen) <= 300),
  created_at timestamptz not null default now()
);
alter table public.propuestas enable row level security;
drop policy if exists "leer propuestas" on public.propuestas;
create policy "leer propuestas" on public.propuestas for select to anon using (true);
drop policy if exists "enviar propuestas" on public.propuestas;
create policy "enviar propuestas" on public.propuestas for insert to anon with check (true);

-- ---------------------------------------------------------------- imágenes de las propuestas
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('propuestas', 'propuestas', true, 5242880,
        array['image/jpeg', 'image/png', 'image/gif', 'image/webp'])
on conflict (id) do update set public = true, file_size_limit = 5242880,
  allowed_mime_types = array['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
drop policy if exists "subir imagenes de propuestas" on storage.objects;
create policy "subir imagenes de propuestas" on storage.objects
  for insert to anon with check (bucket_id = 'propuestas');
