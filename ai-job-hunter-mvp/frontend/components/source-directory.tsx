import { ArrowUpRight, Globe2 } from "lucide-react";

export default function SourceDirectory({
  role,
  country,
}: {
  role: string;
  country: string;
}) {
  const query = encodeURIComponent(role || "Frontend Engineer");
  const location = encodeURIComponent(country);
  const boards = [
    {
      name: "LinkedIn",
      url: `https://www.linkedin.com/jobs/search/?keywords=${query}&location=${location}`,
    },
    {
      name: "Indeed",
      url: `https://de.indeed.com/jobs?q=${query}&l=${location}`,
    },
    { name: "Glassdoor", url: "https://www.glassdoor.com/Job/index.htm" },
    { name: "XING", url: "https://www.xing.com/jobs" },
    { name: "HeyJobs", url: "https://www.heyjobs.co/de-de/jobs" },
    { name: "eFinancialCareers", url: "https://www.efinancialcareers.com/" },
    { name: "EU Remote Jobs", url: "https://euremotejobs.com/" },
    { name: "JobLeads", url: "https://www.jobleads.com/" },
    { name: "GermanTechJobs", url: "https://germantechjobs.de/en" },
  ];
  return (
    <section className="source-directory" aria-labelledby="additional-sources">
      <div className="row">
        <Globe2 size={18} />
        <h2 id="additional-sources">Explore more job boards</h2>
      </div>
      <p className="muted">
        Arbeitnow and GermanTechJobs connect directly. LinkedIn, Indeed,
        Glassdoor, XING, HeyJobs and eFinancialCareers can be queried through
        the TheirStack connection in the Live feed menu, subject to provider
        coverage. These links open the original websites.
      </p>
      <div className="source-links">
        {boards.map((board) => (
          <a key={board.name} href={board.url} target="_blank" rel="noreferrer">
            {board.name}
            <ArrowUpRight size={14} />
            <span className="muted">
              {board.name === "GermanTechJobs"
                ? "Live RSS available"
                : "Search on website"}
            </span>
          </a>
        ))}
      </div>
    </section>
  );
}
