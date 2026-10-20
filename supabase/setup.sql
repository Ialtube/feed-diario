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

-- ---------------------------------------------------------------- sorteo de la grieta
-- Cada boleto: un nombre y tres números del 0 al 99. La fecha la pone siempre el servidor.
create table if not exists public.boletos (
  id bigint generated always as identity primary key,
  nombre text not null check (char_length(nombre) between 1 and 40),
  numeros smallint[] not null check (array_length(numeros, 1) = 3 and 0 <= all(numeros) and 99 >= all(numeros)),
  created_at timestamptz not null default now()
);
alter table public.boletos enable row level security;
drop policy if exists "leer boletos" on public.boletos;
create policy "leer boletos" on public.boletos for select to anon using (true);
drop policy if exists "comprar boletos" on public.boletos;
-- nadie puede colar un boleto con fecha antigua para un sorteo ya celebrado
create policy "comprar boletos" on public.boletos for insert to anon
  with check (created_at between now() - interval '2 minutes' and now() + interval '2 minutes');

-- ---------------------------------------------------------------- comentarios en cada noticia
-- pieza vacía = comentario a la edición entera («Cartas al director»)
alter table public.comentarios add column if not exists pieza integer;

-- ---------------------------------------------------------------- reacciones a las noticias
-- Cada navegador puede poner cada emoji una vez por noticia (no se pueden quitar).
create table if not exists public.reacciones (
  id bigint generated always as identity primary key,
  edicion date not null,
  pieza integer not null,
  emoji text not null check (emoji in ('😂', '💀', '🔥', '🤡', '🧂', '👑')),
  lector text not null check (char_length(lector) between 8 and 60),
  nombre text check (nombre is null or char_length(nombre) <= 40),
  created_at timestamptz not null default now(),
  unique (edicion, pieza, emoji, lector)
);
alter table public.reacciones enable row level security;
drop policy if exists "leer reacciones" on public.reacciones;
create policy "leer reacciones" on public.reacciones for select to anon using (true);
drop policy if exists "reaccionar" on public.reacciones;
create policy "reaccionar" on public.reacciones for insert to anon
  with check (created_at between now() - interval '2 minutes' and now() + interval '2 minutes');

-- ---------------------------------------------------------------- visitas
-- Quién abre cada página (con el nombre que eligió el lector, o anónimo). Una por día y página.
create table if not exists public.visitas (
  id bigint generated always as identity primary key,
  pagina text not null check (char_length(pagina) between 1 and 80),
  nombre text check (nombre is null or char_length(nombre) <= 40),
  lector text check (lector is null or char_length(lector) <= 60),
  created_at timestamptz not null default now()
);
alter table public.visitas enable row level security;
drop policy if exists "leer visitas" on public.visitas;
create policy "leer visitas" on public.visitas for select to anon using (true);
drop policy if exists "visitar" on public.visitas;
create policy "visitar" on public.visitas for insert to anon
  with check (created_at between now() - interval '2 minutes' and now() + interval '2 minutes');

-- Hace que la API vea las tablas nuevas al momento
notify pgrst, 'reload schema';
