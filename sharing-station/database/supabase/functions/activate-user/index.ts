import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const supabase = createClient(
  Deno.env.get('SUPABASE_URL')!,
  Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
)

Deno.serve(async (req) => {
  if (req.method !== 'POST') {
    return new Response('Method not allowed', { status: 405 })
  }

  const { nfc_uuid } = await req.json()
  if (!nfc_uuid) {
    return new Response(JSON.stringify({ error: 'nfc_uuid is required' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  // Deactivate all users
  const { error: deactivateError } = await supabase
    .from('users')
    .update({ is_active: false })
    .eq('is_active', true)

  if (deactivateError) {
    return new Response(JSON.stringify({ error: deactivateError.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  // Activate the user with the given NFC UUID
  const { data, error } = await supabase
    .from('users')
    .update({ is_active: true })
    .eq('nfc_uuid', nfc_uuid)
    .select()
    .single()

  if (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  if (!data) {
    return new Response(JSON.stringify({ error: 'User not found' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  return new Response(JSON.stringify(data), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
})
