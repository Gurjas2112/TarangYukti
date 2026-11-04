import { MfaGate } from "../../src/components/MfaGate.web";
import { AdminScreen } from "../../src/screens/AdminScreen.web";

export default function Admin() {
  return (
    <MfaGate roles={["platform_admin"]}>
      <AdminScreen />
    </MfaGate>
  );
}
