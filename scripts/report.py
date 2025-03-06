from compare_releases import max_version, min_version


class Report:
    def __init__(self, components):
        self.components = components

    def __str__(self):
        return str(self.to_dict())

    @classmethod
    def from_dict(cls, d):
        return cls({f"{c['name']}-{c['component_version']}-{c['openlineage_version']}": Component.from_dict(c) for c in d})

    @classmethod
    def single_component_report(cls, component):
        return cls({component.name: component})

    def get_tag_summary(self):
        return {k: v.get_tag_summary() for k, v in self.components.items()}

    def get_new_failures(self, old):
        oc = old.components if old is not None and old.components is not None else {}
        return Report({k: nfc for k, v in self.components.items() if
                       (nfc := v.get_new_failures(oc.get(k))) is not None})

    def update(self, new):
        if len(self.components) == 0:
            self.components = new.components
        else:
            for k, v in new.components.items():
                if self.components.keys().__contains__(k):
                    self.components[k].update(v)
                else:
                    self.components[k] = v

    def to_dict(self):
        return [c.to_dict() for c in self.components.values()]


class Component:

    def __init__(self, name, component_type, scenarios, component_version, openlineage_version):
        self.name = name
        self.component_type = component_type
        self.scenarios = scenarios
        self.component_version = component_version
        self.openlineage_version = openlineage_version

    def __str__(self):
        return str(self.to_dict())

    @classmethod
    def from_dict(cls, d):
        return cls(d['name'], d['component_type'],
                   {s['name']: Scenario.from_dict(s) for s in d['scenarios']}, d['component_version'],
                   d['openlineage_version'])

    def get_tag_summary(self):
        facets = {}
        inputs = {}
        for n, s in self.scenarios.items():
            ss = s.get_tag_summary(self.component_type)
            for f, ver in ss['facets'].items():
                s.update_facet_versions(f, facets, ver['max_version'], ver['min_version'])
            if self.component_type == 'producer':
                for datasource, lineage_levels in ss['lineage_levels'].items():
                    for ll, ver in lineage_levels.items():
                        if inputs.get(datasource) is None:
                            inputs[datasource] = {}
                        s.update_facet_versions(ll, inputs[datasource], ver['max_version'], ver['min_version'])
            else:
                for i, ver in ss['producers'].items():
                    s.update_facet_versions(i, inputs, ver['max_version'], ver['min_version'])
        output = {'facets': facets}
        if self.component_type == 'producer':
            output["lineage_levels"] = inputs
        else:
            output["producers"] = inputs
        return output

    def get_new_failures(self, old):
        os = old.scenarios if old is not None and old.scenarios is not None else {}
        nfs = {k: nfs for k, v in self.scenarios.items() if
               (nfs := v.get_new_failures(os.get(k))) is not None}
        return Component(self.name, self.component_type, nfs, self.component_version, self.openlineage_version) if any(nfs) else None

    def update(self, new):
        for k, v in new.scenarios.items():
            if self.scenarios.keys().__contains__(k):
                self.scenarios[k].update(v)
            else:
                self.scenarios[k] = v

    def to_dict(self):
        return {'name': self.name, 'component_type': self.component_type, 'component_version': self.component_version,
                'openlineage_version': self.openlineage_version,
                'scenarios': [c.to_dict() for c in self.scenarios.values()]}


class Scenario:

    def __str__(self):
        return str(self.to_dict())

    def __init__(self, name, status, tests):
        self.name = name
        self.status = status
        self.tests = tests

    @classmethod
    def simplified(cls, name, tests):
        tests_ = tests if isinstance(tests, dict) else {t.name: t for t in tests}
        return cls(name, 'SUCCESS' if not any(t for n, t in tests_.items() if t.status == 'FAILURE') else 'FAILURE',
                   tests_)

    @classmethod
    def from_dict(cls, d):
        return cls(d['name'], d['status'], {t['name']: Test.from_dict(t) for t in d['tests']})

    def get_tag_summary(self, component_type):
        facets = {}
        inputs = {}
        for name, test in self.tests.items():
            if test.status == 'SUCCESS' and len(test.tags) > 0:
                tags = test.tags
                min_ver = tags.get('min_version')
                max_ver = tags.get('max_version')
                for f in tags['facets']:
                    self.update_facet_versions(f, facets, max_ver, min_ver)

                if component_type == 'producer':
                    lineage_levels = tags['lineage_level'].items() if 'lineage_level' in tags else {}
                    for datasource, lineage_levels in lineage_levels:
                        for ll in lineage_levels:
                            if inputs.get(datasource) is None:
                                inputs[datasource] = {}
                            self.update_facet_versions(ll, inputs[datasource], max_ver, min_ver)
                if component_type == 'consumer':
                    # if inputs.get(tags['producer']) is None:
                    #     inputs[tags['producer']] = {}
                    self.update_facet_versions(tags['producer'], inputs, max_ver, min_ver)
        output = {'facets': facets}
        if component_type == 'producer':
            output["lineage_levels"] = inputs
        else:
            output["producers"] = inputs
        return output

    def update_facet_versions(self, f, entity, max_ver, min_ver):
        if entity.get(f) is None:
            entity[f] = {'max_version': max_ver, 'min_version': min_ver}
        else:
            entity[f]['max_version'] = max_version(max_ver, entity[f].get('max_version'))
            entity[f]['min_version'] = min_version(min_ver, entity[f].get('min_version'))

    def get_new_failures(self, old):
        if self.status == 'SUCCESS':
            return None
        ot = old.tests if old is not None and old.tests is not None else {}
        nft = {k: nft for k, v in self.tests.items() if (nft := v.get_new_failure(ot.get(k))) is not None}
        return Scenario(self.name, self.status, nft) if any(nft) else None

    def update(self, new):
        self.status = new.status
        for k, v in new.tests.items():
            if self.tests.keys().__contains__(k):
                self.tests[k].update(v)
            else:
                self.tests[k] = v

    def to_dict(self):
        return {'name': self.name, 'status': self.status, 'tests': [t.to_dict() for t in self.tests.values()]}


class Test:
    def __init__(self, name, status, validation_type, entity_type, details, tags):
        self.name = name
        self.status = status
        self.validation_type = validation_type
        self.entity_type = entity_type
        self.details = details
        self.tags = tags

    def __str__(self):
        return str(self.to_dict())

    @classmethod
    def simplified(cls, name, validation_type, entity_type, details, tags):
        return cls(name, 'SUCCESS' if len(details) == 0 else 'FAILURE', validation_type, entity_type, details, tags)

    @classmethod
    def from_dict(cls, d):
        return cls(d['name'], d['status'], d['validation_type'], d['entity_type'],
                   d['details'] if d.__contains__('details') else [], d['tags'])

    def get_new_failure(self, old):
        if self.status == 'FAILURE':
            if old is None or old.status == 'SUCCESS' or any(
                    d for d in self.details if not old.details.__contains__(d)):
                return self
        return None

    def update(self, new):
        self.status = new.status
        self.details = new.details
        self.tags = new.tags

    def to_dict(self):
        return {"name": self.name, "status": self.status, "validation_type": self.validation_type,
                "entity_type": self.entity_type, "details": self.details, "tags": self.tags}
