using ParserModule.Visitors;

namespace ParserModule.Nodes;

public sealed class ExternFunctionDeclarationNode : ModuleLevelStatementNode
{
    public override void Accept(IModuleLevelNodeVisitor visitor)
    {
        visitor.VisitExternFunctionDeclaration(this);
    }

    public required FunctionSignature Signature { get; init; }
}